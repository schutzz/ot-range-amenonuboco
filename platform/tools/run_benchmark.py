#!/usr/bin/env python3
"""Phase12: 高負荷環境でのパフォーマンス測定ベンチマークハーネス。

manifests/stress-test-reference.yaml を対象に、シナリオA/B/Cごとに
負荷生成用資産を起動し、Elasticsearchへ実際に到達したドキュメント数から
スループット（eps）と、クライアント側のログ行数（＝アプリケーション層で
完了したことが確認できたラウンドトリップ数）との比較でロス率を算出する。

【旧版からの修正点（罠ログ参照）】
- 旧版はcompose生成物を`-o manifests/stress.yaml`のように明示的に
  `manifests/`直下・`.yaml`拡張子で出力しており、(1) `manifests/*.yaml`を
  グロブする回帰テストがマニフェストと誤認してエラーになる、
  (2) `.gitignore`の`*.docker-compose.yml`パターンにも掛からず誤って
  コミットされうる、という二重の事故を誘発していた。本版は`cli.py provision`
  の既定命名（`<manifest>.docker-compose.yml`）をそのまま使う。
- 旧版は`docker compose start/stop`のみで、実際に負荷レベル（pps）を
  変えるパラメータが存在しなかった。本版は`--interval`で各プロトコル
  資産のポーリング間隔を上書きでき、複数の負荷レベルを実際に計測できる
  （ただし各プロトコル資産の`env_int()`がINTERVAL="0.05"のような小数秒を
  ValueErrorで黙って握りつぶし既定の5秒間隔にフォールバックしていたバグを
  先に修正済み。修正前はここで何を指定しても無意味だった）。
- 旧版はElasticsearchの`_count`のみを見ており、「送信した数」を一切
  計測していなかったため、ロス率は原理的に算出不能だった。本版は
  クライアントコンテナのログから完了ラウンドトリップ数を数え、
  「送信（アプリ層で完了確認できた数）」対「ES到達数」の比でロス率を出す。
  ログ行数ベースの近似であり、tsharkの再構成率まで含む完全な検証では
  ないことに注意（詳細はスクリプト末尾のREADME的コメント参照）。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "manifests" / "stress-test-reference.yaml"
# cli.py既定命名。manifests/直下だが拡張子が.ymlのため`manifests/*.yaml`の
# 回帰テストグロブにも.gitignoreの`*.docker-compose.yml`にも安全に収まる。
COMPOSE_FILE = REPO_ROOT / "manifests" / "stress-test-reference.docker-compose.yml"

ES_URL = "http://localhost:9200"

# シナリオごとの資産構成。
# client: 負荷生成側サービス名（複数可）。
# server: 対向サービス名（複数可、起動のみ行う）。
# index: 到達確認に使うESインデックスパターン。
# count_pattern: クライアントのログから「アプリ層で完了したラウンド
#   トリップ」を数えるための grep パターン（プロトコルごとに実際のログ
#   文言を確認した上で選定、Phase12再計測時に検証済み）。
SCENARIOS = {
    "A": {
        "clients": ["sc_a_modbus_client"],
        "servers": ["sc_a_modbus_server"],
        "index": "ot-logs-modbus-*",
        "count_pattern": "wrote",
    },
    "B": {
        "clients": ["sc_b_opcua_client", "sc_b_dnp3_client"],
        "servers": ["sc_b_opcua_server", "sc_b_dnp3_server"],
        "index": "ot-logs-opcua-*,ot-logs-dnp3-*",
        "count_pattern": None,  # クライアントごとにパターンが違うため個別指定（下記参照）
    },
    "C": {
        "clients": ["sc_c_profinet_client1", "sc_c_profinet_client2"],
        "servers": [],  # L2ブロードキャストのみ。専用の受信側資産は無い
        "index": "ot-logs-pn_rt-*",
        "count_pattern": "Sent PROFINET RT Frame",
    },
}

# シナリオBはプロトコルごとにログ文言が違うため、クライアントサービス名 -> パターン
CLIENT_COUNT_PATTERNS = {
    "sc_a_modbus_client": "wrote",
    "sc_b_opcua_client": "wrote",
    "sc_b_dnp3_client": "response from",
    "sc_c_profinet_client1": "Sent PROFINET RT Frame",
    "sc_c_profinet_client2": "Sent PROFINET RT Frame",
}


def sh(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)


def get_es_count(index: str) -> int:
    """カンマ区切りの複数インデックスパターンに対応。"""
    total = 0
    for idx in index.split(","):
        req = urllib.request.Request(f"{ES_URL}/{idx.strip()}/_count")
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                data = json.loads(res.read().decode())
                total += data.get("count", 0)
        except urllib.error.URLError as e:
            print(f"Warning: Failed to reach Elasticsearch ({idx}): {e}")
    return total


def wait_for_es(timeout_s: int = 60) -> bool:
    print("Waiting for Elasticsearch to become available...")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(ES_URL, timeout=3) as res:
                if res.status == 200:
                    print("Elasticsearch is ready.")
                    return True
        except Exception:
            pass
        time.sleep(2)
    print("Elasticsearch did not become ready.")
    return False


def compose(
    *args: str, project: str = "amenonuboco-bench", batch_size: int | None = None
) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "-p", project, *args]
    env = None
    if batch_size is not None:
        env = os.environ | {"BULK_LOADER_BATCH_SIZE": str(batch_size)}
    return sh(cmd, env=env)


def wait_for_count_stable(
    index: str, timeout_s: float, poll_interval_s: float, stable_polls: int
) -> tuple[int, bool]:
    """ESの件数が連続して変化しなくなるまで待ち、最終到達数を返す。"""
    if timeout_s <= 0 or poll_interval_s <= 0 or stable_polls < 1:
        raise ValueError("settle timeout/interval must be positive and stable polls >= 1")

    print(
        "Waiting for Elasticsearch count to settle "
        f"(timeout={timeout_s:g}s, interval={poll_interval_s:g}s, stable={stable_polls})..."
    )
    deadline = time.monotonic() + timeout_s
    previous: int | None = None
    consecutive = 0
    current = get_es_count(index)
    while True:
        if current == previous:
            consecutive += 1
            if consecutive >= stable_polls:
                print(f"Elasticsearch count settled at {current}.")
                return current, True
        else:
            previous = current
            consecutive = 0
        if time.monotonic() >= deadline:
            print(f"Elasticsearch count did not settle; using latest count {current}.")
            return current, False
        time.sleep(poll_interval_s)
        current = get_es_count(index)


def container_name(service: str, project: str = "amenonuboco-bench") -> str:
    return f"{project}-{service}-1"


def count_client_log_lines(
    service: str, pattern: str, since: float, project: str = "amenonuboco-bench"
) -> int:
    """`docker logs --since <since>`で、このシナリオ実行が始まった時刻以降の
    行だけを数える。

    【罠ログ参照】旧版は`--since`を指定せず、コンテナ起動からの累積ログ全体を
    数えていた。`run_benchmark.py`は`compose up -d`でコンテナを使い回す
    （既に起動中のサービスに対しては何もしない）ため、同じコンテナに対して
    シナリオを複数回実行すると、2回目以降は前回までの行が「送信数」に
    混入し、実際には起きていないロスを人為的に作り出していた。ES側の
    到達数は`get_es_count()`で最初から正しくdelta（差分）計測していたのに、
    クライアント側だけ累積値を使うという非対称な集計になっていたのが原因。
    `--since`でDocker自身に時刻フィルタさせることで、ES側と同じ「この実行
    分だけ」を測る設計に揃える。
    """
    name = container_name(service, project)
    proc = subprocess.run(
        ["docker", "logs", "--since", str(since), name],
        capture_output=True, text=True, errors="replace",
    )
    text = proc.stdout + proc.stderr
    return sum(1 for line in text.splitlines() if pattern in line)


def apply_interval_override(interval: float) -> None:
    """マニフェストのINTERVALをその場で書き換えてコンポーズを再生成する。

    複数の負荷レベルを試すための簡易な手段。sed的な文字列置換で済ませており
    YAML構造は変えないため、既存の "INTERVAL=<数値>" という1行フォーマットに
    依存する（stress-test-reference.yaml側の記法が変わったら追随が必要）。
    """
    import re
    text = MANIFEST.read_text(encoding="utf-8")
    text2 = re.sub(r'"INTERVAL=[0-9.]+"', f'"INTERVAL={interval}"', text)
    if text2 == text:
        print(f"Warning: INTERVAL override didn't match anything (interval={interval})")
    MANIFEST.write_text(text2, encoding="utf-8")


def regenerate_compose() -> None:
    sh([
        sys.executable, str(REPO_ROOT / "platform" / "cli.py"),
        "provision", str(MANIFEST),
        # -o を渡さない = 既定命名(<manifest>.docker-compose.yml)を使う。
        # 罠ログ参照: -o で manifests/ 直下に .yaml 拡張子で出すと、
        # 回帰テストのグロブ・.gitignore の両方の安全機構を迂回してしまう。
    ])


def run_scenario(
    scenario: str,
    duration: int,
    interval: float | None,
    batch_size: int,
    settle_timeout: float,
    settle_poll_interval: float,
    settle_stable_polls: int,
) -> dict:
    cfg = SCENARIOS[scenario]
    clients = cfg["clients"]
    servers = cfg["servers"]

    if interval is not None:
        apply_interval_override(interval)
        regenerate_compose()

    print(f"--- Starting Scenario {scenario} (interval={interval}) ---")

    if not wait_for_es():
        return {"scenario": scenario, "error": "elasticsearch not ready"}

    initial_count = get_es_count(cfg["index"])
    print(f"Initial doc count: {initial_count}")

    # `--since`用の基準時刻。compose up直前に取得する（コンテナが使い回され
    # 既に起動中の場合、up -dは何もしないため、この時刻以降のログだけを
    # 数えれば「今回の実行分」を正しく切り出せる）。
    run_start_ts = int(time.time())

    compose("up", "-d", *servers, *clients, batch_size=batch_size)

    print(f"Running for {duration} seconds...")
    time.sleep(duration)

    # クライアント側の完了ラウンドトリップ数を、停止する前にログから数える
    sent = 0
    for c in clients:
        pattern = CLIENT_COUNT_PATTERNS.get(c, cfg["count_pattern"] or "")
        n = count_client_log_lines(c, pattern, since=run_start_ts)
        print(f"  {c}: {n} lines matching '{pattern}'")
        sent += n

    compose("stop", *clients, *servers, batch_size=batch_size)

    final_count, settled = wait_for_count_stable(
        cfg["index"], settle_timeout, settle_poll_interval, settle_stable_polls
    )
    received = final_count - initial_count
    throughput = received / duration
    loss_pct = max(0.0, (sent - received) / sent * 100) if sent > 0 else None

    result = {
        "scenario": scenario,
        "interval": interval,
        "duration_s": duration,
        "sent_confirmed": sent,
        "es_received": received,
        "throughput_eps": round(throughput, 2),
        "loss_pct": round(loss_pct, 2) if loss_pct is not None else None,
        "batch_size": batch_size,
        "es_count_settled": settled,
    }
    print(f"--- Result: {json.dumps(result, ensure_ascii=False)} ---")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Amenonuboco Performance Benchmark Harness (v2)")
    parser.add_argument("--scenario", "-s", choices=["A", "B", "C"], required=True)
    parser.add_argument("--duration", "-d", type=int, default=30)
    parser.add_argument(
        "--interval", "-i", type=float, default=None,
        help="対象プロトコルのポーリング間隔[秒]でマニフェストを上書きしてから実行する。"
             "省略時はマニフェストに既に書かれている値のまま実行する。",
    )
    parser.add_argument(
        "--setup", action="store_true",
        help="計測前にベース基盤（router/elasticsearch/structurer）を起動する。",
    )
    parser.add_argument("--batch-size", type=int, default=50, help="bulk_loaderのES投入バッチ件数")
    parser.add_argument("--settle-timeout", type=float, default=60.0)
    parser.add_argument("--settle-poll-interval", type=float, default=2.0)
    parser.add_argument("--settle-stable-polls", type=int, default=3)
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error("--batch-size must be >= 1")

    if not COMPOSE_FILE.exists() or args.setup:
        regenerate_compose()

    if args.setup:
        compose(
            "up", "-d", "wan_router", "elasticsearch", "log_structurer",
            batch_size=args.batch_size,
        )
        if not wait_for_es():
            sys.exit(1)

    result = run_scenario(
        args.scenario, args.duration, args.interval, args.batch_size,
        args.settle_timeout, args.settle_poll_interval, args.settle_stable_polls,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

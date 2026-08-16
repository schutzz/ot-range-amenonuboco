#!/usr/bin/env python3
"""tsharkの`-T ek`出力(標準入力)を読み、指定したElasticsearch indexへ
`_bulk` APIでバッチ投入する軽量ラッパー(Phase3決定事項#40)。

責務はバッファリング+定期POSTのみに限定する。プロトコル解釈・フィールド
加工は行わない(tshark自身の`-T ek`出力の構造化に委ねる)。標準ライブラリ
のみで動く(構造化ノードのベースイメージに追加のpip installを要求しない)。

`-T ek`はアクション行(`{"index": {...}}`)とドキュメント行が交互に並ぶ形式
だが、アクション行のindex名はtshark側が独自に決めるため、このスクリプトが
`--index`で指定された値に置き換えてから送信する。

既知の制約(Phase3の最小スコープとして許容): flush-intervalによる時間
ベースのフラッシュは、次の標準入力行が届いた時点でしかチェックされない
(トラフィックが疎らな場合、実際のタイマー的な定期フラッシュにはならない)。
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.request


def _resolve_concrete_index(pattern: str) -> str:
    """`ot-logs-http-*`のようなワイルドカードindexパターン(Phase0決定事項#5、
    Kibana/Grafana側の検索用index patternとして確立済み)から、実際に書き込む
    先の具体的な日次index名を導出する。

    Elasticsearchの`_bulk` APIは`_index`にワイルドカードを含む名前を許可せず、
    そのまま渡すと400 Bad Requestになる(Phase3決定事項#49、罠ログ#012)。
    前身`ot-ids-verum`のvector.tomlが確立した`<name>-%Y.%m.%d`という日次の
    具体的index名規則(例: `bulk.index = "ot-logs-http-%Y.%m.%d"`)をそのまま
    踏襲し、末尾の`*`をUTC日付に置き換える。
    """
    base = pattern[:-1] if pattern.endswith("*") else pattern + "-"
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y.%m.%d")
    return base + today


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True, help="投入先のElasticsearch index名")
    parser.add_argument("--es-url", required=True, help="例: http://elasticsearch:9200")
    parser.add_argument("--batch-size", type=int, default=50, help="この件数溜まったらフラッシュ")
    parser.add_argument("--flush-interval", type=float, default=5.0, help="秒単位")
    args = parser.parse_args()

    bulk_url = args.es_url.rstrip("/") + "/_bulk"
    buffer: list[str] = []
    doc_count = 0
    last_flush = time.monotonic()

    def flush() -> None:
        nonlocal buffer, last_flush, doc_count
        if not buffer:
            last_flush = time.monotonic()
            return
        body = ("\n".join(buffer) + "\n").encode("utf-8")
        req = urllib.request.Request(
            bulk_url,
            data=body,
            headers={"Content-Type": "application/x-ndjson"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
        except urllib.error.HTTPError as exc:
            # レスポンス本文にElasticsearchのエラー詳細(マッピング競合等)が
            # 入っているため、診断のために出力する(罠ログ#012の調査で確立)。
            print(f"bulk_loader: POST failed: {exc} body={exc.read()!r}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - 監視ノードを止めないため広く捕捉しログのみ
            print(f"bulk_loader: POST failed: {exc}", file=sys.stderr)
        buffer = []
        doc_count = 0
        last_flush = time.monotonic()

    pending_is_action = True
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if pending_is_action and "index" in obj:
            concrete_index = _resolve_concrete_index(args.index)
            buffer.append(json.dumps({"index": {"_index": concrete_index}}))
            pending_is_action = False
            # ここではflush判定を行わない。アクション行だけを積んだ状態
            # (対になるドキュメント行がまだ届いていない)でflushすると、
            # 末尾がアクション行だけの不完全な_bulkボディを送ることになり、
            # Elasticsearchが"no requests added"で拒否する(罠ログ#018)。
            # HTTPのような高頻度トラフィックでは次のドキュメント行がすぐ
            # 届くため気づきにくいが、DNP3のような疎なトラフィックで
            # flush_interval(既定5秒)がアクション行の直後に経過すると
            # 顕在化する。
        else:
            buffer.append(json.dumps(obj))
            doc_count += 1
            pending_is_action = True
            # flush判定はドキュメント行を積んで「完全な1組」になった
            # 直後にのみ行う。これによりbufferは常にアクション/ドキュメント
            # の完全な組だけを保持した状態でflushされる。
            if doc_count >= args.batch_size or (time.monotonic() - last_flush) >= args.flush_interval:
                flush()

    flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

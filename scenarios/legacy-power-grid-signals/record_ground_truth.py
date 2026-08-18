#!/usr/bin/env python3
"""record_ground_truth.py — Signal1(ゾーン逸脱)の正解ラベルを記録する
評価ハーネス側スクリプト(Phase5決定事項#69【訂正版】)。

**攻撃者ノードからは実行しない**。攻撃者コンテナ自身が正解ラベルをESへ
書き込む設計は、前身`ot-ids-verum`が排除しようとした「OOB自己申告」
(`oob_redis`/`oob_webdis`)と本質的に同じ構図になってしまう——「侵害された
かもしれない側が、自分は攻撃したと申告する」構造だからである。

正解ラベルは「演習を実行した側(オペレータ/評価ハーネス)が独立に記録するもの」
であるべきで、`eval_harness`資産(cc_lan接続、role: eval-harness)から実行する
ことを前提にする。標準ライブラリのみで動く。

罠ログ#017: 当初`dnp3_zone_attack.py`(攻撃者ノード側)が直接この責務を持って
いたが、`sub_a_l2_lan`のみに接続する攻撃者コンテナは`cc_lan`上の`elasticsearch`
へ名前解決できない(Docker既定のサービスディスカバリは同一ネットワーク内の
コンテナにしか及ばない)という実機エラーに遭遇し、責務分離が本来あるべき
設計だったと判明した。
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.error
import urllib.request


def record(es_url: str, src_ip: str, dst_ip: str, expected_violation: bool) -> None:
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y.%m.%d")
    index = f"signal1-ground-truth-{today}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    doc = {
        # Elasticsearchの標準タイムスタンプフィールド名に揃える
        # (Phase6実装時にzone_violation.pyで発見した抜けと同じ理由、
        # Grafana等の時系列可視化がこのフィールド名を前提にするため)。
        "@timestamp": now_iso,
        "timestamp": now_iso,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "expected_violation": expected_violation,
    }
    body = json.dumps(doc).encode("utf-8")
    req = urllib.request.Request(
        f"{es_url.rstrip('/')}/{index}/_doc",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()
    print(f"[+] ground truth recorded: {doc}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src-ip", required=True)
    parser.add_argument("--dst-ip", required=True)
    parser.add_argument("--es-url", default="http://elasticsearch:9200")
    parser.add_argument(
        "--expect-violation",
        dest="expect_violation",
        action="store_true",
        default=True,
    )
    parser.add_argument(
        "--no-expect-violation", dest="expect_violation", action="store_false"
    )
    args = parser.parse_args()

    try:
        record(args.es_url, args.src_ip, args.dst_ip, args.expect_violation)
    except urllib.error.URLError as exc:
        print(f"[!] ground truth write failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

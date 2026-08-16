#!/usr/bin/env python3
"""evaluate_signal1.py — Signal1(ゾーン逸脱)の評価ハーネス最小実装(Phase5決定事項#69)。

`signal1-ground-truth-*`(dnp3_zone_attack.pyが書いた正解ラベル)と
`ot-signals-zone-violation-*`(zone_violation.pyが書いたアラート)を突き合わせ、
「攻撃を撃った送信元IPに対して、検知が実際に発火したか」を報告する。

前身`ot-ids-verum`の評価ハーネス(`oob_redis`/`oob_webdis`、io.popen+curl方式)は
Phase0決定事項#13の通り持ち込まない。OOB自己申告ではなく、双方とも
Elasticsearchへ書かれた観測事実同士を突き合わせる方式に作り直した(前身の
「観測事実だけで判定する」という原点をむしろ徹底した形になる)。

Phase5の最小スコープ: 「1攻撃に1検知が正しく対応したか」の単純な突き合わせに
留める(複数シナリオ・統計的評価はPhase6以降)。標準ライブラリのみで動く。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def _search(es_url: str, index_pattern: str, size: int = 50) -> list[dict]:
    # "timestamp"へのソートはtext型フィールドのfielddata無効化で失敗する
    # (罠ログ#019)。挿入順(_doc)を使う。
    body = json.dumps({"size": size, "sort": ["_doc"]}).encode("utf-8")
    req = urllib.request.Request(
        f"{es_url.rstrip('/')}/{index_pattern}/_search",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        # index未作成(まだ1件も書き込みが無い)場合は404になりうる。空扱いにする。
        if exc.code == 404:
            return []
        raise
    return [hit["_source"] for hit in data.get("hits", {}).get("hits", [])]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--es-url", default="http://elasticsearch:9200")
    args = parser.parse_args()

    ground_truths = _search(args.es_url, "signal1-ground-truth-*")
    alerts = _search(args.es_url, "ot-signals-zone-violation-*")

    alert_sources = {a.get("src_ip") for a in alerts if a.get("signal") == "signal-1-zone-violation"}

    print(f"正解ラベル件数: {len(ground_truths)}")
    print(f"検知アラート件数: {len(alerts)}")
    print()

    matched = 0
    mismatched = 0
    for gt in ground_truths:
        src_ip = gt.get("src_ip")
        expected = gt.get("expected_violation")
        detected = src_ip in alert_sources
        ok = detected == expected
        matched += ok
        mismatched += not ok
        status = "OK " if ok else "NG "
        print(
            f"[{status}] src={src_ip} expected_violation={expected} "
            f"detected={detected}"
        )

    print()
    print(f"一致: {matched} / 不一致: {mismatched} / 合計: {matched + mismatched}")
    return 0 if mismatched == 0 and matched > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

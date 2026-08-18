#!/usr/bin/env python3
"""zone_violation.py — Signal1(ゾーン逸脱)検知sidecar。

前身`ot-ids-verum`のVector VRL(`enrich_trace`transform内のallowlistルックアップ、
`vector/vector.toml`の`allowlist_hit = get_enrichment_table_record("ot_allowlist", ...)`)
を、Amenonubocoの検知プラグイン機構(sidecar)向けにPythonへ書き直したもの
(Phase5決定事項#68)。

判定ロジックは前身と同一の意味論: DNP3トラフィックの送信元IPが許可リストに
無ければゾーン逸脱として検知する。前身の`ot_allowlist.csv`は実際には
"許可された送信元IP1件のみ"の単純な許可リストだった(`10.0.10.10,eng-workstation-01,
IT_ENG`の1行のみ)。Phase5計画時点ではセグメント間フロー方式(`cc_lan->sub_b_lan`
のような組)を想定していたが、実装時に前身の実データを確認しこちらへ補正した
(前身の実データに忠実であることを優先、決定事項#68)。

責務はバッファリングを持たない単純な定期ポーリングに限定する(Phase3決定事項
#40のバルクローダーと同じく、判定ロジック以外の複雑さを持ち込まない)。
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import time

import requests

ES_URL = os.environ.get("ES_URL", "http://elasticsearch:9200")
ALLOWED_SOURCES = {
    ip.strip()
    for ip in os.environ.get("ALLOWED_DNP3_SOURCES", "").split(",")
    if ip.strip()
}
POLL_INTERVAL_SEC = 5
SRC_INDEX_PATTERN = "ot-logs-dnp3-*"
ALERT_INDEX_BASE = "ot-signals-zone-violation"

# 直近に評価済みのdocument _id。ESの自動生成IDは新規投入のたびに変わるため、
# 同じDNP3パケットを毎周期再評価して重複アラートを出すことを防ぐ
# (前身killchain_eql_pollerが同種の重複防止をtime-rangeフィルタで行っていた
# のと同じ目的、ここではdocument _idの記憶という単純な方式を採る)。
_seen_ids: set[str] = set()


def _alert_index() -> str:
    """アラート出力先の日次index名(前身のvector.tomlと同じ`-%Y.%m.%d`規則、
    Phase3決定事項#49と同じ導出方式)。
    """
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y.%m.%d")
    return f"{ALERT_INDEX_BASE}-{today}"


def _to_iso8601(tshark_timestamp: str | None) -> str:
    """tshark -T ek が出力する epoch millis文字列("1786889321633"のような
    値)を、ElasticsearchがdateとしてマッピングするISO8601形式へ変換する。
    変換できない場合は現在時刻にフォールバックする(監視ノードを止めない)。
    """
    if tshark_timestamp is not None:
        try:
            epoch_ms = int(tshark_timestamp)
            return datetime.datetime.fromtimestamp(
                epoch_ms / 1000, tz=datetime.timezone.utc
            ).isoformat()
        except (TypeError, ValueError):
            pass
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def poll_once() -> int:
    """新規に到着したDNP3パケットを走査し、ゾーン逸脱を検知したらESへ書き出す。
    戻り値: 今回発火した検知件数。
    """
    query = {
        "size": 50,
        # "timestamp"はtshark -T ekが文字列として書き込むフィールドで、ES側の
        # 動的マッピングでtext型になる(数値のように見えても引用符付きの
        # 文字列であるため)。text型フィールドは既定でfielddataが無効化されて
        # おりソートに使えない(実機で"Fielddata is disabled"エラーを確認、
        # 罠ログ#019)。新着順である必要は無い(直近のポーリング窓内に限られる
        # 前提)ため、常に使えるインデックス挿入順(_doc)でソートする。
        "sort": ["_doc"],
        "query": {"wildcard": {"layers.frame.frame_frame_protocols": "*dnp3*"}},
    }
    try:
        resp = requests.post(f"{ES_URL}/{SRC_INDEX_PATTERN}/_search", json=query, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        # インデックスが未作成(まだDNP3パケットが1件も構造化されていない)の
        # 場合も含めて広く捕捉する。sidecarは監視ノードなので落ちてはいけない。
        print(f"[zone_violation] search failed: {exc}", file=sys.stderr)
        return 0

    hits = resp.json().get("hits", {}).get("hits", [])
    bulk_lines: list[str] = []
    fired = 0

    for hit in hits:
        doc_id = hit["_id"]
        if doc_id in _seen_ids:
            continue
        _seen_ids.add(doc_id)

        layers = hit.get("_source", {}).get("layers", {})
        src_ip = layers.get("ip", {}).get("ip_ip_src")
        dst_ip = layers.get("ip", {}).get("ip_ip_dst")
        if src_ip is None:
            continue

        if src_ip not in ALLOWED_SOURCES:
            fired += 1
            bulk_lines.append(json.dumps({"index": {"_index": _alert_index()}}))
            bulk_lines.append(
                json.dumps(
                    {
                        # Phase6実装時に発見(罠ログ#089相当): 元のtshark由来
                        # "timestamp"はepoch millisの文字列であり、Elasticsearch
                        # の動的マッピングでtext型になる(罠#019と同型)ため、
                        # Grafana等の時系列パネルが時間軸として認識できない。
                        # Elasticsearchが標準で日付型と推定するISO8601形式の
                        # "@timestamp"を追加する(killchain_eql_poller.pyは
                        # 前身から移植した時点で既に@timestampを持っていた
                        # ため、この欠落はzone_violation.py新規実装時のみの
                        # 抜けだった)。
                        "@timestamp": _to_iso8601(hit["_source"].get("timestamp")),
                        "timestamp": hit["_source"].get("timestamp"),
                        "signal": "signal-1-zone-violation",
                        "src_ip": src_ip,
                        "dst_ip": dst_ip,
                        "allowed_sources": sorted(ALLOWED_SOURCES),
                        "source_dnp3_doc_id": doc_id,
                    }
                )
            )
            print(
                f"[zone_violation] ALERT: unauthorized DNP3 source {src_ip} -> {dst_ip}",
                file=sys.stderr,
            )

    if bulk_lines:
        body = ("\n".join(bulk_lines) + "\n").encode("utf-8")
        try:
            r = requests.post(
                f"{ES_URL}/_bulk",
                data=body,
                headers={"Content-Type": "application/x-ndjson"},
                timeout=10,
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as exc:
            print(f"[zone_violation] bulk write failed: {exc}", file=sys.stderr)

    return fired


def main() -> int:
    print(
        f"[zone_violation] starting, poll every {POLL_INTERVAL_SEC}s, "
        f"allowed_sources={sorted(ALLOWED_SOURCES)}",
        file=sys.stderr,
    )
    while True:
        poll_once()
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())

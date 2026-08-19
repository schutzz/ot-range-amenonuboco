#!/usr/bin/env python3
"""SNMP のエージェント（機器の管理インターフェース役）とポーラ（NMS役）。

サイバーレンジの資産として置くための最小実装。環境変数で役割と接続先を
変えられるようにしてあり、同じイメージを複数の分野・複数の資産で使い回す
(使い方は docs/protocol-assets.md)。

環境変数:
    MODE       agent | poller       （既定: agent。server/client も可）
    PORT       待ち受け/接続先ポート（既定: 161）
    TARGET     接続先IP（poller時のみ必須）
    INTERVAL   ポーリング間隔[秒]   （既定: 5）
    COMMUNITY  コミュニティ文字列   （既定: public）
    VERSION    1 | 2c               （既定: 2c）
    SYSLOCATION / SYSCONTACT / SYSNAME  エージェントが公開する識別情報
    LABEL      ログに出す識別名     （既定: snmp）

**実装方針**：本物の net-snmp（`snmpd` / `snmpget` / `snmpwalk` / `snmpset`）を
使う。SNMPを自作する必然性は無く、むしろ「実際の運用で使われている実装が
生成するパケット」であることに価値がある。ここでのPythonは、役割の切り替えと
環境変数の解釈だけを担当する薄い包みにすぎない。

**認証情報は既定のまま（community "public"）**にしてある。SNMPv1/v2cは
コミュニティ文字列を平文で送るため、観測すれば認証情報がそのまま見える。
初期設定を変更しないまま露出した管理インターフェースという、実際に
繰り返し問題になっている構図を、そのまま再現するための設定である。
"""

from __future__ import annotations

import os
import random
import subprocess
import sys
import time

# ポーラが読みに行くOID。機器の素性（sysDescr）・稼働時間（sysUpTime）・
# 識別名（sysName）・設置場所（sysLocation）という、NMSが実際に集める情報。
_POLL_OIDS = [
    ("sysDescr", "1.3.6.1.2.1.1.1.0"),
    ("sysUpTime", "1.3.6.1.2.1.1.3.0"),
    ("sysContact", "1.3.6.1.2.1.1.4.0"),
    ("sysName", "1.3.6.1.2.1.1.5.0"),
    ("sysLocation", "1.3.6.1.2.1.1.6.0"),
]

# 書き込み対象。sysLocation は snmpd のビルドによっては設定ファイルで
# 静的に指定されていると notWritable で拒否されるため、こちらは
# 設定ファイルに書かず、SET で初めて値が入る状態にしてある。
_WRITE_OID = ("sysContact", "1.3.6.1.2.1.1.4.0")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name) or default)
    except ValueError:
        return default


LABEL = env("LABEL", "snmp")
PORT = env_int("PORT", 161)
COMMUNITY = env("COMMUNITY", "public")
VERSION = env("VERSION", "2c")


def log(message: str) -> None:
    print(f"[{LABEL}] {message}", flush=True)


def run_agent() -> None:
    location = env("SYSLOCATION", "Amenonuboco Cyber Range")
    name = env("SYSNAME", LABEL)

    # sysContact は書かない（SET の対象にするため。上記 _WRITE_OID のコメント参照）。
    config = (
        f"rwcommunity {COMMUNITY}\n"
        f"agentAddress udp:{PORT}\n"
        f"sysLocation {location}\n"
        f"sysName {name}\n"
        "sysServices 72\n"
    )
    with open("/etc/snmp/snmpd.conf", "w", encoding="utf-8") as handle:
        handle.write(config)

    log(f"SNMP agent listening on 0.0.0.0:{PORT}/udp (community={COMMUNITY})")
    # snmpd をこのプロセスに置き換える。PID 1 のまま前景実行することで、
    # docker stop のシグナルがそのまま届き、ログも標準出力へ出る。
    os.execvp("snmpd", ["snmpd", "-f", "-Lo", "-C", "-c", "/etc/snmp/snmpd.conf"])


def _snmp(tool: str, target: str, args: list[str]) -> tuple[bool, str]:
    command = [
        tool,
        f"-v{VERSION}",
        "-c",
        COMMUNITY,
        "-t",
        "3",
        "-r",
        "1",
        f"{target}:{PORT}",
        *args,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    output = (result.stdout or result.stderr).strip().splitlines()
    return result.returncode == 0, output[0] if output else ""


def run_poller() -> None:
    target = env("TARGET")
    if not target:
        log("TARGET が未設定です（MODE=poller では接続先IPが必須）")
        sys.exit(1)

    interval = env_int("INTERVAL", 5)
    log(f"polling {target}:{PORT} every {interval}s (v{VERSION}, community={COMMUNITY})")

    rounds = 0
    while True:
        rounds += 1
        for name, oid in _POLL_OIDS:
            ok, line = _snmp("snmpget", target, [oid])
            # エージェント側の起動待ちで最初の数回は失敗しうる。異常終了させず、
            # 次の周期で再試行する（起動順序に依存しない器にするため）。
            log(f"GET {name}: {line}" if ok else f"GET {name} failed: {line}")

        # インターフェース一覧のwalkも回す。GETが1問1答なのに対しwalkは
        # GET-NEXTの連鎖になり、構造化した時に別種の要求として現れる。
        ok, line = _snmp("snmpwalk", target, ["1.3.6.1.2.1.2.2.1.2"])
        log(f"WALK ifDescr: {line}" if ok else f"WALK ifDescr failed: {line}")

        # 4巡に1回、書き込みを混ぜる。SET は GET とは別のPDU種別になるため、
        # 構造化した時に「読まれたのか書かれたのか」の区別が現れる。
        if rounds % 4 == 0:
            name, oid = _WRITE_OID
            value = f"ops-{random.randint(1000, 9999)}@example.invalid"
            ok, line = _snmp("snmpset", target, [oid, "s", value])
            log(f"SET {name} = {value}" if ok else f"SET {name} failed: {line}")

        time.sleep(interval)


def main() -> None:
    mode = env("MODE", "agent").lower()
    if mode in ("agent", "server"):
        run_agent()
    elif mode in ("poller", "client"):
        run_poller()
    else:
        log(f"未知の MODE '{mode}'（agent または poller を指定してください）")
        sys.exit(1)


if __name__ == "__main__":
    main()

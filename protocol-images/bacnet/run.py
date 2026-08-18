#!/usr/bin/env python3
"""BACnet/IP の機器役（デバイス）と監視役（クライアント）。

サイバーレンジの資産として置くための最小実装。環境変数で役割と接続先を
変えられるようにしてあり、同じイメージを複数の分野・複数の資産で使い回す
(使い方は docs/protocol-assets.md)。

環境変数:
    MODE      device | client       （既定: device）
    PORT      待ち受け/送信先ポート （既定: 47808）
    TARGET    送信先IP（client時のみ必須。ブロードキャストアドレスも可）
    INTERVAL  送信間隔[秒]          （既定: 5）
    DEVICE_ID BACnetデバイスインスタンス番号（既定: 1）
    LABEL     ログに出す識別名      （既定: bacnet）

**実装方針**：BACnet/IPのフレームをライブラリに頼らず生のバイト列で組み立てる。
BACnet用のPythonライブラリは非同期APIが込み入っており、バージョン間の
変更も大きい。一方でBACnet/IPのフレーム構造（BVLC＋NPDU＋APDU）は単純で、
必要なサービス（Who-Is / I-Am / ReadProperty）に限れば数十バイトで表現できる。
**送信するバイト列を完全に把握できる**ことは、構造化パイプラインが何を
解析しているかを検証する上でも利点になる。
"""

from __future__ import annotations

import os
import random
import socket
import struct
import sys
import time


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name) or default)
    except ValueError:
        return default


LABEL = env("LABEL", "bacnet")
PORT = env_int("PORT", 47808)
DEVICE_ID = env_int("DEVICE_ID", 1)


def log(message: str) -> None:
    print(f"[{LABEL}] {message}", flush=True)


# --- フレーム組み立て --------------------------------------------------------
#
# BVLC(BACnet Virtual Link Control):
#   0x81            Type: BACnet/IP
#   func            0x0A=Original-Unicast-NPDU / 0x0B=Original-Broadcast-NPDU
#   length(2byte)   BVLCヘッダを含む全長
# NPDU:
#   0x01            Version
#   control         0x20=宛先指定あり / 0x00=なし
#   (宛先指定ありの場合) DNET(2byte) DLEN(1byte) Hop(1byte)

_BVLC_UNICAST = 0x0A
_BVLC_BROADCAST = 0x0B


def _frame(apdu: bytes, broadcast: bool) -> bytes:
    if broadcast:
        npdu = bytes([0x01, 0x20, 0xFF, 0xFF, 0x00, 0xFF])
        func = _BVLC_BROADCAST
    else:
        npdu = bytes([0x01, 0x00])
        func = _BVLC_UNICAST
    body = npdu + apdu
    return bytes([0x81, func]) + struct.pack(">H", 4 + len(body)) + body


def who_is() -> bytes:
    """Unconfirmed-Request / who-Is（サービス選択 0x08）。"""
    return _frame(bytes([0x10, 0x08]), broadcast=True)


def i_am(device_instance: int, vendor_id: int = 15) -> bytes:
    """Unconfirmed-Request / i-Am（サービス選択 0x00）。

    BACnetObjectIdentifier は上位10bitがオブジェクト種別（8=device）、
    下位22bitがインスタンス番号。
    """
    obj_id = (8 << 22) | (device_instance & 0x3FFFFF)
    apdu = (
        bytes([0x10, 0x00])
        + bytes([0xC4])
        + struct.pack(">I", obj_id)  # BACnetObjectIdentifier
        + bytes([0x22, 0x01, 0xE0])  # 最大APDU長 480
        + bytes([0x91, 0x00])  # セグメンテーション: both
        + bytes([0x21, vendor_id & 0xFF])  # ベンダーID
    )
    return _frame(apdu, broadcast=True)


def read_property(device_instance: int, invoke_id: int, prop_id: int = 85) -> bytes:
    """Confirmed-Request / readProperty（サービス選択 0x0C）。

    prop_id の既定 85 は present-value（現在値）。監視システムが機器の値を
    読みに行く、という最も普通の振る舞いにあたる。
    """
    obj_id = (8 << 22) | (device_instance & 0x3FFFFF)
    apdu = (
        bytes([0x00, 0x05, invoke_id & 0xFF, 0x0C])
        + bytes([0x0C])
        + struct.pack(">I", obj_id)  # コンテキストタグ0: オブジェクト識別子
        + bytes([0x19, prop_id & 0xFF])  # コンテキストタグ1: プロパティ識別子
    )
    return _frame(apdu, broadcast=False)


def read_property_ack(invoke_id: int, device_instance: int, value: int) -> bytes:
    """ComplexACK / readProperty の応答。"""
    obj_id = (8 << 22) | (device_instance & 0x3FFFFF)
    apdu = (
        bytes([0x30, invoke_id & 0xFF, 0x0C])
        + bytes([0x0C])
        + struct.pack(">I", obj_id)
        + bytes([0x19, 0x55])  # プロパティ識別子: present-value
        + bytes([0x3E])  # 開きタグ3
        + bytes([0x44])
        + struct.pack(">f", float(value))  # Real
        + bytes([0x3F])  # 閉じタグ3
    )
    return _frame(apdu, broadcast=False)


# --- 役割 --------------------------------------------------------------------


def run_device() -> None:
    """待ち受けて、Who-Is には I-Am を、ReadProperty には値を返す。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", PORT))
    log(f"BACnet/IP device listening on 0.0.0.0:{PORT} (instance={DEVICE_ID})")

    while True:
        try:
            data, addr = sock.recvfrom(1500)
        except Exception as exc:  # noqa: BLE001
            log(f"recv error: {exc}")
            continue
        if len(data) < 6 or data[0] != 0x81:
            continue

        # NPDUのcontrolバイトから、APDUの開始位置を求める
        npdu_start = 4
        control = data[npdu_start + 1]
        apdu_start = npdu_start + (6 if control & 0x20 else 2)
        apdu = data[apdu_start:]
        if not apdu:
            continue

        pdu_type = apdu[0] & 0xF0
        if pdu_type == 0x10 and len(apdu) > 1 and apdu[1] == 0x08:
            log(f"Who-Is from {addr[0]} -> replying I-Am")
            sock.sendto(i_am(DEVICE_ID), (addr[0], PORT))
        elif pdu_type == 0x00 and len(apdu) > 3 and apdu[3] == 0x0C:
            invoke_id = apdu[2]
            value = random.randint(180, 240)  # 例: 温度・圧力などのプロセス値
            log(f"ReadProperty from {addr[0]} -> present-value={value}")
            sock.sendto(read_property_ack(invoke_id, DEVICE_ID, value), (addr[0], PORT))


def run_client() -> None:
    """定期的に Who-Is をブロードキャストし、ReadProperty を送る。"""
    target = env("TARGET")
    if not target:
        log("TARGET が未設定です（MODE=client では送信先IPが必須）")
        sys.exit(1)

    interval = env_int("INTERVAL", 5)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", PORT))
    sock.settimeout(2)
    log(f"polling {target}:{PORT} every {interval}s (instance={DEVICE_ID})")

    invoke_id = 0
    while True:
        try:
            sock.sendto(who_is(), (target, PORT))
            log("sent Who-Is")
            invoke_id = (invoke_id + 1) % 256
            sock.sendto(read_property(DEVICE_ID, invoke_id), (target, PORT))
            log(f"sent ReadProperty (invoke_id={invoke_id})")

            # 応答を拾ってログに出す（届いていることを目視で確かめられるように）
            deadline = time.time() + 2
            while time.time() < deadline:
                try:
                    data, addr = sock.recvfrom(1500)
                except socket.timeout:
                    break
                log(f"received {len(data)} bytes from {addr[0]}")
        except Exception as exc:  # noqa: BLE001
            log(f"unexpected error: {exc}")
        time.sleep(interval)


def main() -> None:
    mode = env("MODE", "device").lower()
    if mode in ("device", "server"):
        run_device()
    elif mode == "client":
        run_client()
    else:
        log(f"未知の MODE '{mode}'（device または client を指定してください）")
        sys.exit(1)


if __name__ == "__main__":
    main()

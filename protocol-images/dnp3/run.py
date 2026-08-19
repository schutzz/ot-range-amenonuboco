#!/usr/bin/env python3
"""DNP3 (IEEE 1815) over TCP のアウトステーション（機器役）とマスタ（監視役）。

サイバーレンジの資産として置くための最小実装。環境変数で役割と接続先を
変えられるようにしてあり、同じイメージを複数の分野・複数の資産で使い回す
(使い方は docs/protocol-assets.md)。

環境変数:
    MODE       outstation | master   （既定: outstation。server/client も可）
    PORT       待ち受け/接続先ポート （既定: 20000）
    TARGET     接続先IP（master時のみ必須）
    INTERVAL   ポーリング間隔[秒]    （既定: 5）
    DEVICE_ID  自局アドレス          （既定: outstation=10 / master=1）
    PEER_ID    相手局アドレス        （既定: outstation=1 / master=10）
    POINTS     アナログ入力の点数    （既定: 3）
    LABEL      ログに出す識別名      （既定: dnp3）

**実装方針**：フレームをライブラリに頼らず生のバイト列で組み立てる。
DNP3のPython実装は薄く、C++バインディングを要するものが多い。一方で
必要なサービス（Integrity Poll / Response / Direct Operate）に限れば、
データリンク層＋トランスポート層＋アプリケーション層を数十バイトで
表現できる。**送信するバイト列を完全に把握できる**ことは、構造化
パイプラインが何を解析しているかを検証する上でも利点になる。

マスタは周期的に Class 0/1/2/3 のIntegrity Pollを投げ、時々
Direct Operate（CROB＝リレー出力制御）を送る。読み取りと制御指令が
別のファンクションコードとして現れるため、構造化した時に「何をされたか」の
区別が生まれる。
"""

from __future__ import annotations

import os
import random
import socket
import struct
import sys
import time

# --- データリンク層 ----------------------------------------------------------
#
# フレーム構造:
#   0x05 0x64 | LEN(1) | CTRL(1) | DEST(2,LE) | SRC(2,LE) | CRC(2,LE)
#   その後、ユーザデータを16バイトごとのブロックに切り、各ブロック末尾にCRC(2)
#
# LEN は CTRL から ユーザデータ末尾 までのバイト数（CRC群と 0x0564・LEN 自身を
# 含まない）＝ 5 + len(payload)。

_START = b"\x05\x64"
_BLOCK = 16

# DNP3のCRC。多項式 0x3D65 の反転 0xA6BC を使い、最後に1の補数を取る。
# 汎用のCRC-16とは別物であり、ここを間違えるとtsharkが
# "corrupt header checksum" として解析を放棄する（＝構造化されない）。
_CRC_POLY = 0xA6BC


def _crc(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ _CRC_POLY if crc & 1 else crc >> 1
    return (~crc) & 0xFFFF


def _with_crc(data: bytes) -> bytes:
    return data + struct.pack("<H", _crc(data))


def build_frame(dest: int, src: int, control: int, payload: bytes) -> bytes:
    header = _START + bytes([5 + len(payload), control]) + struct.pack(
        "<HH", dest & 0xFFFF, src & 0xFFFF
    )
    frame = _with_crc(header)
    for offset in range(0, len(payload), _BLOCK):
        frame += _with_crc(payload[offset : offset + _BLOCK])
    return frame


def frame_length(length_field: int) -> int:
    """LENフィールドから、フレーム全体のバイト数を求める。"""
    user_len = length_field - 5
    blocks = (user_len + _BLOCK - 1) // _BLOCK
    return 10 + user_len + 2 * blocks


def parse_frame(raw: bytes) -> tuple[int, int, int, bytes]:
    """(control, dest, src, payload) を返す。CRCは検証せず読み飛ばす。"""
    control = raw[3]
    dest, src = struct.unpack("<HH", raw[4:8])
    payload = b""
    body = raw[10:]
    for offset in range(0, len(body), _BLOCK + 2):
        payload += body[offset : offset + _BLOCK]
    return control, dest, src, payload[: raw[2] - 5]


# データリンク制御バイト。DIR(0x80)は「マスタ発」を意味し、PRM(0x40)は
# 一次局からの送信を示す。下位4bitはリンク層ファンクション（3=無確認ユーザデータ）。
CTRL_FROM_MASTER = 0xC4
CTRL_FROM_OUTSTATION = 0x44

# トランスポート層（1バイト）：FIR|FIN|シーケンス番号。分割送信はしないため常に両方立てる。
TRANSPORT_SINGLE = 0xC0

# アプリケーション層ファンクションコード
FUNC_READ = 0x01
FUNC_DIRECT_OPERATE = 0x05
FUNC_RESPONSE = 0x81


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name) or default)
    except ValueError:
        return default


LABEL = env("LABEL", "dnp3")
PORT = env_int("PORT", 20000)
POINTS = env_int("POINTS", 3)


def log(message: str) -> None:
    print(f"[{LABEL}] {message}", flush=True)


# --- アプリケーション層のペイロード ------------------------------------------


def integrity_poll(seq: int) -> bytes:
    """Class 0/1/2/3 の全読み出し。マスタが最初に投げる定番の要求。

    オブジェクトグループ60（Class Data）の変化点1〜3とスタティック0を、
    修飾子 0x06（全オブジェクト・範囲指定なし）で並べる。
    """
    app = bytes([0xC0 | (seq & 0x0F), FUNC_READ])
    for variation in (1, 2, 3, 4):
        app += bytes([60, variation, 0x06])
    return bytes([TRANSPORT_SINGLE | (seq & 0x1F)]) + app


def direct_operate(seq: int, index: int, control_code: int = 0x41) -> bytes:
    """Direct Operate（CROB＝リレー出力ブロック）。

    制御コードは下位4bitが動作種別、上位2bitがTrip/Closeコード。既定の
    0x41 は「Pulse On ＋ Close」＝**遮断器を投入する指令**にあたる
    （tsharkでは dnp3.al.ctl.op=1 / dnp3.al.ctl.trip=1 として現れる）。
    読み取り要求とは明確に別のファンクションコードとして観測されるため、
    検知ロジックを書く側にとって最も関心の高い通信になる。
    """
    app = bytes([0xC0 | (seq & 0x0F), FUNC_DIRECT_OPERATE])
    app += bytes([12, 1, 0x17, 1, index & 0xFF])  # g12v1, 1オクテット計数+索引
    app += bytes([control_code, 1])  # 制御コード, 実行回数
    app += struct.pack("<II", 100, 100)  # オン時間・オフ時間[ms]
    app += bytes([0x00])  # 状態
    return bytes([TRANSPORT_SINGLE | (seq & 0x1F)]) + app


def analog_response(seq: int, values: list[int]) -> bytes:
    """Response（g30v1＝32bitアナログ入力・フラグ付き）。"""
    app = bytes([0xC0 | (seq & 0x0F), FUNC_RESPONSE, 0x00, 0x00])  # IIN=正常
    app += bytes([30, 1, 0x00, 0, max(len(values) - 1, 0)])  # 開始〜終了索引
    for value in values:
        app += bytes([0x01]) + struct.pack("<i", value)  # フラグ: online
    return bytes([TRANSPORT_SINGLE | (seq & 0x1F)]) + app


def null_response(seq: int) -> bytes:
    """オブジェクトを伴わない応答（制御指令の受理応答に使う）。"""
    app = bytes([0xC0 | (seq & 0x0F), FUNC_RESPONSE, 0x00, 0x00])
    return bytes([TRANSPORT_SINGLE | (seq & 0x1F)]) + app


# --- ストリームからのフレーム切り出し ----------------------------------------


def read_frame(sock: socket.socket, buffer: bytearray) -> bytes | None:
    """TCPはフレーム境界を保たないため、LENフィールドを見て切り出す。"""
    while True:
        start = buffer.find(_START)
        if start > 0:
            del buffer[:start]
        elif start < 0:
            buffer.clear()
        if len(buffer) >= 3:
            total = frame_length(buffer[2])
            if len(buffer) >= total:
                frame = bytes(buffer[:total])
                del buffer[:total]
                return frame
        chunk = sock.recv(4096)
        if not chunk:
            return None
        buffer.extend(chunk)


# --- 役割 --------------------------------------------------------------------


def run_outstation() -> None:
    own = env_int("DEVICE_ID", 10)
    peer = env_int("PEER_ID", 1)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", PORT))
    listener.listen(5)
    log(f"DNP3 outstation listening on 0.0.0.0:{PORT} (addr={own}, points={POINTS})")

    while True:
        conn, addr = listener.accept()
        log(f"master connected from {addr[0]}")
        buffer = bytearray()
        try:
            while True:
                frame = read_frame(conn, buffer)
                if frame is None:
                    break
                _ctrl, _dest, src, payload = parse_frame(frame)
                if len(payload) < 3:
                    continue
                seq = payload[1] & 0x0F
                func = payload[2]
                if func == FUNC_READ:
                    values = [random.randint(0, 4095) for _ in range(POINTS)]
                    log(f"READ (integrity poll) from {src} -> {values}")
                    conn.sendall(
                        build_frame(
                            peer, own, CTRL_FROM_OUTSTATION, analog_response(seq, values)
                        )
                    )
                elif func == FUNC_DIRECT_OPERATE:
                    log(f"DIRECT OPERATE from {src} -> acknowledging")
                    conn.sendall(
                        build_frame(peer, own, CTRL_FROM_OUTSTATION, null_response(seq))
                    )
                else:
                    log(f"unhandled function code 0x{func:02x} from {src}")
        except Exception as exc:  # noqa: BLE001 - レンジ資産は落とさず回し続ける
            log(f"session error: {exc}")
        finally:
            conn.close()
            log("master disconnected")


def run_master() -> None:
    target = env("TARGET")
    if not target:
        log("TARGET が未設定です（MODE=master では接続先IPが必須）")
        sys.exit(1)

    own = env_int("DEVICE_ID", 1)
    peer = env_int("PEER_ID", 10)
    interval = env_int("INTERVAL", 5)
    log(f"polling {target}:{PORT} every {interval}s (addr={own} -> {peer})")

    seq = 0
    polls = 0
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        try:
            sock.connect((target, PORT))
        except OSError as exc:
            # アウトステーション側の起動待ちで最初の数回は失敗しうる。異常終了
            # させず、次の周期で再試行する（起動順序に依存しない器にするため）。
            log(f"connect failed to {target}:{PORT} ({exc}), retrying")
            sock.close()
            time.sleep(interval)
            continue

        buffer = bytearray()
        try:
            while True:
                seq = (seq + 1) & 0x0F
                polls += 1
                # 4回に1回は制御指令を混ぜる。読み取りだけが延々流れる状態より、
                # 「稀に起きる制御」を含む方が、検知ロジックの検証対象として現実的。
                if polls % 4 == 0:
                    log("sending DIRECT OPERATE (CROB close, index=0)")
                    sock.sendall(
                        build_frame(peer, own, CTRL_FROM_MASTER, direct_operate(seq, 0))
                    )
                else:
                    log("sending READ (integrity poll, class 0/1/2/3)")
                    sock.sendall(
                        build_frame(peer, own, CTRL_FROM_MASTER, integrity_poll(seq))
                    )

                frame = read_frame(sock, buffer)
                if frame is None:
                    log("outstation closed the connection, reconnecting")
                    break
                _ctrl, _dest, src, payload = parse_frame(frame)
                log(f"response from {src} ({len(payload)} bytes of application data)")
                time.sleep(interval)
        except Exception as exc:  # noqa: BLE001
            log(f"session error: {exc}, reconnecting")
        finally:
            sock.close()
            time.sleep(interval)


def main() -> None:
    mode = env("MODE", "outstation").lower()
    if mode in ("outstation", "server"):
        run_outstation()
    elif mode in ("master", "client"):
        run_master()
    else:
        log(f"未知の MODE '{mode}'（outstation または master を指定してください）")
        sys.exit(1)


if __name__ == "__main__":
    main()

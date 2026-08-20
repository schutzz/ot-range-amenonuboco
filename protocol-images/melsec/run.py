#!/usr/bin/env python3
"""三菱 MELSEC MC プロトコル（SLMP 3E フレーム）の PLC 役とクライアント役。

MC プロトコル 3E フレームの構成:
  サブヘッダ (2B): 0x0050 (3E binary)
  ネットワーク番号 (1B): 0x00
  PC 番号 (1B): 0xFF
  要求先ユニット I/O 番号 (2B): 0x03FF
  要求先ユニット局番号 (1B): 0x00
  データ長 (2B): 後続バイト数
  CPU 監視タイマ (2B): 0x0004 (4 * 250ms = 1s)
  コマンド (2B): 0x0401=読み取り / 0x1401=書き込み
  サブコマンド (2B): 0x0000
  先頭デバイス番号 (3B): リトルエンディアン
  デバイス種別 (1B): 0xA8=D (データレジスタ)
  点数 (2B): ワード数

tshark での捕捉:
  ネイティブ dissector 非対応。TCP ポート 5007 のトラフィックを
  `tcp.port == 5007` で捕捉し、output_index に保存する。
  dissector_plugins に Lua プラグインを指定すれば SLMP 解析が可能
  （Phase11 Stage1C の dissector_plugins 配線機構で自動マウント）。

環境変数:
    MODE      server | client        （既定: server）
    PORT      待ち受け/接続先ポート  （既定: 5007）
    TARGET    接続先IP（client 時のみ必須）
    INTERVAL  ポーリング間隔[秒]     （既定: 5）
    LABEL     ログに出す識別名       （既定: melsec）
"""

from __future__ import annotations

import os
import random
import socket
import struct
import sys
import time
import threading


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name) or default)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    # env_int()はint()でパースするため"0.05"のような小数秒はValueErrorで
    # 黙ってdefaultにフォールバックしてしまう（Phase12罠、負荷試験で
    # INTERVAL=0.05を指定しても無視され既定の5秒間隔で動いていた）。
    # 秒単位の間隔（INTERVAL等）は必ずこちらを使う。
    try:
        return float(env(name) or default)
    except ValueError:
        return default


LABEL = env("LABEL", "melsec")
PORT = env_int("PORT", 5007)

# データレジスタ (D デバイス) のシミュレーション。
# クライアントは D100〜D107 を読み書きするため、その範囲を含むサイズにする。
_D_SIZE = 128
# 3E バイナリフレームのサブヘッダ（要求／応答で異なる）
_SUBHEADER = b"\x50\x00"       # 要求（クライアント→PLC）
_RESP_SUBHEADER = b"\xD0\x00"  # 応答（PLC→クライアント）
# 固定フィールド（ネットワーク・PC・ユニット・局番）
_FIXED_ROUTING = b"\x00\xFF\xFF\x03\x00"
_CPU_TIMER = b"\x04\x00"  # 4 * 250ms = 1s
_CMD_READ = b"\x01\x04"   # 0x0401
_CMD_WRITE = b"\x01\x14"  # 0x1401
_SUBCMD = b"\x00\x00"
_DEVICE_D = 0xA8  # D デバイス（データレジスタ）


def log(message: str) -> None:
    print(f"[{LABEL}] {message}", flush=True)


def _build_3e_request(command: bytes, device_no: int, count: int, data: bytes = b"") -> bytes:
    """3E バイナリ要求フレームを構築する。"""
    # デバイス番号: 3 バイト リトルエンディアン + デバイス種別 1B
    dev_field = struct.pack("<I", device_no)[:3] + bytes([_DEVICE_D])
    word_count = struct.pack("<H", count)

    body = _CPU_TIMER + command + _SUBCMD + dev_field + word_count + data
    data_len = struct.pack("<H", len(body))

    return _SUBHEADER + _FIXED_ROUTING + data_len + body


def _recv_3e_frame(sock: socket.socket) -> bytes | None:
    """3E フレームを受信して本文（データ長以降）を返す。"""
    # 最低 9 バイトのヘッダ（subheader 2 + routing 5 + data_len 2）
    header = b""
    while len(header) < 9:
        chunk = sock.recv(9 - len(header))
        if not chunk:
            return None
        header += chunk

    # 要求（0x50 0x00）・応答（0xD0 0x00）のどちらでも受信できるようにする。
    # このヘルパーはサーバ（要求を受信）とクライアント（応答を受信）の両方から
    # 共用されているため、片方のサブヘッダしか許容しないと応答側の受信が
    # 常に失敗し、コネクションが読み取り1回ごとに切断・再接続を繰り返す。
    if header[:2] not in (_SUBHEADER, _RESP_SUBHEADER):
        return None

    data_len = struct.unpack("<H", header[7:9])[0]
    body = b""
    while len(body) < data_len:
        chunk = sock.recv(data_len - len(body))
        if not chunk:
            return None
        body += chunk
    return body


def _build_3e_response(end_code: int, data: bytes = b"") -> bytes:
    """3E バイナリ応答フレームを構築する。"""
    # 応答サブヘッダ: 0xD0 0x00
    resp_subheader = b"\xD0\x00"
    body = struct.pack("<H", end_code) + data
    data_len = struct.pack("<H", len(body))
    return resp_subheader + _FIXED_ROUTING + data_len + body


# ---------------------------------------------------------------------------
# サーバ（PLC 役）
# ---------------------------------------------------------------------------

def _handle_client(conn: socket.socket, addr: tuple, d_regs: list[int]) -> None:
    log(f"accepted from {addr}")
    try:
        conn.settimeout(30)
        while True:
            body = _recv_3e_frame(conn)
            if body is None:
                break
            if len(body) < 10:
                break

            # body: CPU_TIMER(2) + CMD(2) + SUBCMD(2) + dev_field(4) + word_count(2) + [write_data]
            command = body[2:4]
            dev_no = struct.unpack("<I", body[6:9] + b"\x00")[0]
            word_count = struct.unpack("<H", body[10:12])[0]

            if command == _CMD_READ:
                count = min(word_count, _D_SIZE - dev_no, 16)
                data = b"".join(struct.pack("<H", d_regs[dev_no + i]) for i in range(count))
                conn.sendall(_build_3e_response(0x0000, data))
                log(f"read D[{dev_no}:{dev_no+count}] -> {list(d_regs[dev_no:dev_no+count])}")

            elif command == _CMD_WRITE:
                for i in range(min(word_count, _D_SIZE - dev_no)):
                    offset = 12 + i * 2
                    if offset + 2 > len(body):
                        break
                    d_regs[dev_no + i] = struct.unpack("<H", body[offset:offset + 2])[0]
                conn.sendall(_build_3e_response(0x0000))
                log(f"wrote D[{dev_no}:{dev_no+word_count}]")
            else:
                log(f"unknown command: {command.hex()}")
                conn.sendall(_build_3e_response(0xC059))  # エラーコード
    except (OSError, socket.timeout):
        pass
    finally:
        conn.close()
        log(f"disconnected: {addr}")


def run_server() -> None:
    d_regs = [random.randint(0, 9999) for _ in range(_D_SIZE)]

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(8)
    log(f"MELSEC MC server (3E binary) listening on 0.0.0.0:{PORT} (D regs={_D_SIZE})")

    while True:
        conn, addr = srv.accept()
        t = threading.Thread(target=_handle_client, args=(conn, addr, d_regs), daemon=True)
        t.start()


# ---------------------------------------------------------------------------
# クライアント（HMI / SCADA 役）
# ---------------------------------------------------------------------------

def run_client() -> None:
    target = env("TARGET")
    if not target:
        log("TARGET が未設定です（MODE=client では接続先IPが必須）")
        sys.exit(1)

    interval = env_float("INTERVAL", 5)
    log(f"polling {target}:{PORT} every {interval}s (MC protocol 3E binary)")

    while True:
        try:
            with socket.create_connection((target, PORT), timeout=10) as sock:
                log(f"connected to {target}:{PORT}")
                while True:
                    # D100〜D107 を読み取る
                    req = _build_3e_request(_CMD_READ, 100, 8)
                    sock.sendall(req)
                    resp = _recv_3e_frame(sock)
                    if resp is None:
                        break
                    if len(resp) >= 2:
                        end_code = struct.unpack("<H", resp[:2])[0]
                        if end_code == 0 and len(resp) >= 18:
                            values = [struct.unpack("<H", resp[2 + i*2:4 + i*2])[0] for i in range(8)]
                            log(f"read D[100:108] = {values}")

                    # D100 に乱数を書き込む
                    value = random.randint(0, 9999)
                    req = _build_3e_request(_CMD_WRITE, 100, 1, struct.pack("<H", value))
                    sock.sendall(req)
                    resp = _recv_3e_frame(sock)
                    if resp is None:
                        break
                    log(f"wrote D[100] = {value}")

                    time.sleep(interval)

        except (OSError, socket.timeout) as exc:
            log(f"error: {exc}, retrying in {interval}s")
            time.sleep(interval)


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------

def main() -> None:
    mode = env("MODE", "server").lower()
    if mode == "server":
        run_server()
    elif mode == "client":
        run_client()
    else:
        log(f"未知の MODE '{mode}'（server または client を指定してください）")
        sys.exit(1)


if __name__ == "__main__":
    main()

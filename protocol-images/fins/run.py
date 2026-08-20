#!/usr/bin/env python3
"""FINS (オムロン) プロトコルの機器役（サーバ）とポーリング役（クライアント）。

サイバーレンジの資産として置くための最小実装。環境変数で役割と接続先を
変えられるようにしてあり、同じイメージを複数の分野・複数の資産で使い回す
(使い方は docs/protocol-assets.md)。

FINS/TCP は UDP と TCP の2つのトランスポートをサポートするが、Docker の
ブリッジネットワーク上では TCP を使う（UDP は発信元ポートの扱いに注意が
必要であり、演習用としては TCP の方が tshark での捕捉が確実）。

tshark の表示フィルタは `omron`（FINS はオムロン独自プロトコルとして
Wireshark に登録されている）。

環境変数:
    MODE      server | client        （既定: server）
    PORT      待ち受け/接続先ポート  （既定: 9600）
    TARGET    接続先IP（client時のみ必須）
    INTERVAL  ポーリング間隔[秒]     （既定: 5）
    LABEL     ログに出す識別名       （既定: fins）

サーバはメモリエリア (DM チャンネル 0〜7) をシミュレートし、クライアントは
それらを定期的に Read/Write する。両方を配置して初めて実際の FINS コマンドが
流れ、構造化パイプラインが解析する対象が生まれる。
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


LABEL = env("LABEL", "fins")
PORT = env_int("PORT", 9600)

# DM チャンネル数（シミュレーション用メモリエリア）
_DM_SIZE = 32


def log(message: str) -> None:
    print(f"[{LABEL}] {message}", flush=True)


# ---------------------------------------------------------------------------
# FINS/TCP フレーム定数
# ---------------------------------------------------------------------------
# FINS/TCP ヘッダ（8 バイト）:
#   magic[4] = b"FINS"
#   length[4] = uint32 (big-endian) — ヘッダを除くバイト数
#
# FINS コマンドフレームの最小構成（後続 header + data）:
#   ICF  = 0x80  (Client→PLC: command, response required)
#   RSV  = 0x00
#   GCT  = 0x02  (gateway count)
#   DNA  = 0x00  (destination network)
#   DA1  = 0x01  (destination node: PLC)
#   DA2  = 0x00  (destination unit)
#   SNA  = 0x00  (source network)
#   SA1  = 0x01  (source node: HMI)
#   SA2  = 0x00  (source unit)
#   SID  = transaction id (1 byte)
#   MRC  = 0x01  (memory area read)
#   SRC  = 0x01
#   + data (memory area code 1B + start addr 2B + bit pos 1B + count 2B)

_FINS_MAGIC = b"FINS"
_FINS_TCP_HANDSHAKE_CLIENT = _FINS_MAGIC + struct.pack(">I", 12) + struct.pack(">I", 0) + struct.pack(">I", 1)
# server handshake response: FINS + len=12 + cmd=1 + error=0 + server_node=1
_FINS_TCP_HANDSHAKE_SERVER = _FINS_MAGIC + struct.pack(">I", 12) + struct.pack(">I", 1) + struct.pack(">I", 0) + struct.pack(">I", 1)

_MRC_MEMORY_READ = (0x01, 0x01)
_MRC_MEMORY_WRITE = (0x01, 0x02)
_DM_WORD_AREA = 0x82  # DM チャンネル（ワード）


def _build_fins_tcp_frame(fins_payload: bytes) -> bytes:
    """FINS ペイロードを FINS/TCP フレームでラップする。"""
    # FINS/TCP データフレーム: magic + length(4) + cmd(4=2) + error(4=0) + fins_payload
    body = struct.pack(">II", 2, 0) + fins_payload
    return _FINS_MAGIC + struct.pack(">I", len(body)) + body


def _build_fins_header(sid: int, mrc: int, src: int) -> bytes:
    """FINS コマンドヘッダ（10 バイト）を構築する。"""
    return bytes([
        0x80,  # ICF: command, response required
        0x00,  # RSV
        0x02,  # GCT
        0x00,  # DNA
        0x01,  # DA1 (PLC node)
        0x00,  # DA2
        0x00,  # SNA
        0x01,  # SA1 (HMI node)
        0x00,  # SA2
        sid & 0xFF,
        mrc,
        src,
    ])


def _read_dm_command(sid: int, start_ch: int, count: int) -> bytes:
    """メモリエリア読み取りコマンドフレームを構築する。"""
    header = _build_fins_header(sid, _MRC_MEMORY_READ[0], _MRC_MEMORY_READ[1])
    # memory area code(1B) + start addr(2B) + bit position(1B) + count(2B)
    payload = bytes([_DM_WORD_AREA]) + struct.pack(">H", start_ch) + bytes([0x00]) + struct.pack(">H", count)
    return _build_fins_tcp_frame(header + payload)


def _write_dm_command(sid: int, start_ch: int, values: list[int]) -> bytes:
    """メモリエリア書き込みコマンドフレームを構築する。"""
    header = _build_fins_header(sid, _MRC_MEMORY_WRITE[0], _MRC_MEMORY_WRITE[1])
    payload = (
        bytes([_DM_WORD_AREA])
        + struct.pack(">H", start_ch)
        + bytes([0x00])
        + struct.pack(">H", len(values))
        + b"".join(struct.pack(">H", v) for v in values)
    )
    return _build_fins_tcp_frame(header + payload)


def _recv_fins_tcp_frame(sock: socket.socket) -> bytes | None:
    """FINS/TCP フレームを受信してペイロード（FINS コマンド部分）を返す。
    接続が切れた場合は None を返す。
    """
    # 8 バイトの FINS/TCP ヘッダを受信
    header_raw = b""
    while len(header_raw) < 8:
        chunk = sock.recv(8 - len(header_raw))
        if not chunk:
            return None
        header_raw += chunk

    magic = header_raw[:4]
    if magic != _FINS_MAGIC:
        return None

    length = struct.unpack(">I", header_raw[4:8])[0]
    body = b""
    while len(body) < length:
        chunk = sock.recv(length - len(body))
        if not chunk:
            return None
        body += chunk
    # body = cmd(4) + error(4) + fins_payload
    if len(body) < 8:
        return None
    return body[8:]  # FINS payload（コマンドヘッダ + データ）


# ---------------------------------------------------------------------------
# サーバ（PLC 役）
# ---------------------------------------------------------------------------

def _handle_client(conn: socket.socket, addr: tuple, dm: list[int]) -> None:
    """接続1本をハンドリングする（スレッドで動く）。"""
    log(f"accepted connection from {addr}")
    try:
        # FINS/TCP ハンドシェイク
        conn.settimeout(10)
        hs = conn.recv(20)
        if not hs or hs[:4] != _FINS_MAGIC:
            log(f"invalid handshake from {addr}")
            return
        conn.sendall(_FINS_TCP_HANDSHAKE_SERVER)

        conn.settimeout(30)
        while True:
            fins = _recv_fins_tcp_frame(conn)
            if fins is None:
                break
            if len(fins) < 12:
                break

            sid = fins[9]
            mrc = fins[10]
            src = fins[11]
            log(f"received MRC={mrc:#04x} SRC={src:#04x} SID={sid} from {addr}")

            if mrc == _MRC_MEMORY_READ[0] and src == _MRC_MEMORY_READ[1]:
                # Read: area(1) + start(2) + bit(1) + count(2)
                if len(fins) < 18:
                    break
                start = struct.unpack(">H", fins[13:15])[0]
                count = struct.unpack(">H", fins[16:18])[0]
                count = min(count, _DM_SIZE - start, 8)
                data = b"".join(struct.pack(">H", dm[start + i]) for i in range(count))
                # Response header: ICF=0xC0, MRC, SRC, end_code(2B=0x0000)
                resp_header = bytes([0xC0, 0x00, 0x02, 0x00, 0x01, 0x00, 0x00, 0x01, 0x00, sid, mrc, src, 0x00, 0x00])
                conn.sendall(_build_fins_tcp_frame(resp_header + data))
                log(f"read DM[{start}:{start+count}] -> {list(dm[start:start+count])}")

            elif mrc == _MRC_MEMORY_WRITE[0] and src == _MRC_MEMORY_WRITE[1]:
                # Write: area(1) + start(2) + bit(1) + count(2) + data(2*count)
                if len(fins) < 18:
                    break
                start = struct.unpack(">H", fins[13:15])[0]
                count = struct.unpack(">H", fins[16:18])[0]
                for i in range(min(count, _DM_SIZE - start)):
                    offset = 18 + i * 2
                    if offset + 2 > len(fins):
                        break
                    dm[start + i] = struct.unpack(">H", fins[offset:offset + 2])[0]
                resp_header = bytes([0xC0, 0x00, 0x02, 0x00, 0x01, 0x00, 0x00, 0x01, 0x00, sid, mrc, src, 0x00, 0x00])
                conn.sendall(_build_fins_tcp_frame(resp_header))
                log(f"wrote DM[{start}:{start+count}]")
    except (OSError, socket.timeout):
        pass
    finally:
        conn.close()
        log(f"connection closed: {addr}")


def run_server() -> None:
    dm = [random.randint(100, 9000) for _ in range(_DM_SIZE)]

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(8)
    log(f"FINS/TCP server listening on 0.0.0.0:{PORT} (DM size={_DM_SIZE})")

    while True:
        conn, addr = srv.accept()
        t = threading.Thread(target=_handle_client, args=(conn, addr, dm), daemon=True)
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
    log(f"polling {target}:{PORT} every {interval}s")

    sid = 0
    while True:
        try:
            with socket.create_connection((target, PORT), timeout=10) as sock:
                # ハンドシェイク
                sock.sendall(_FINS_TCP_HANDSHAKE_CLIENT)
                resp = sock.recv(20)
                if not resp or resp[:4] != _FINS_MAGIC:
                    log(f"handshake failed with {target}:{PORT}")
                    time.sleep(interval)
                    continue
                log(f"connected to {target}:{PORT}")

                while True:
                    # Read DM[0:8]
                    sid = (sid + 1) & 0xFF
                    sock.sendall(_read_dm_command(sid, 0, 8))
                    fins = _recv_fins_tcp_frame(sock)
                    if fins is None:
                        break
                    if len(fins) >= 14:
                        end_code = struct.unpack(">H", fins[12:14])[0]
                        if end_code == 0 and len(fins) >= 30:
                            values = [struct.unpack(">H", fins[14 + i*2:16 + i*2])[0] for i in range(8)]
                            log(f"read DM[0:8] = {values}")
                        else:
                            log(f"read response end_code={end_code:#06x}")

                    # Write DM[0] with random sensor value
                    sid = (sid + 1) & 0xFF
                    value = random.randint(100, 9000)
                    sock.sendall(_write_dm_command(sid, 0, [value]))
                    fins = _recv_fins_tcp_frame(sock)
                    if fins is None:
                        break
                    log(f"wrote DM[0] = {value}")

                    time.sleep(interval)

        except (OSError, socket.timeout) as exc:
            log(f"connect/comm error: {exc}, retrying in {interval}s")
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

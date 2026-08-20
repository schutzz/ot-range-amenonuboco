#!/usr/bin/env python3
"""SECS/GEM HSMS-SS (High-Speed Message Services Single Session) の
Equipment 役（サーバ）と Host 役（クライアント）。

HSMS メッセージヘッダ（10 バイト）:
  Length   (4B, big-endian): ヘッダを含むメッセージ全体のバイト数
  SessionID(2B): 接続セッション識別子
  StatusByte(2B): Byte1=P/SType, Byte2=Function
  HeaderByte8(1B): System Bytes[0]
  HeaderByte9(1B): System Bytes[1]  ← 実際は System Bytes が 4B だが
  System Bytes (4B): トランザクション ID (Length 0x0A + ヘッダのみ)

SEMI E37 HSMS 制御メッセージ:
  Select.req  : SType=0x01
  Select.rsp  : SType=0x02
  Deselect.req: SType=0x03
  Deselect.rsp: SType=0x04
  Linktest.req: SType=0x05
  Linktest.rsp: SType=0x06
  Separate.req: SType=0x09

SECS-II メッセージ (Stream/Function):
  S1F1: Are You There (Host→Equip)
  S1F2: On Line Data  (Equip→Host)
  S6F11: Event Report (Equip→Host, 装置イベント通知)

tshark フィルタ: `hsms`（SECS/GEM HSMS はネイティブ dissector あり）

環境変数:
    MODE        server | client         （既定: server）
    PORT        待ち受け/接続先ポート   （既定: 5000）
    TARGET      接続先IP（client 時のみ必須）
    INTERVAL    メッセージ間隔[秒]      （既定: 10）
    TLS_ENABLE  true の場合 TLS を有効化（既定: false）
    SSLKEYLOGFILE TLS セッションキー書き出しパス（演習用鍵注入）
    LABEL       ログに出す識別名        （既定: secsgem）
"""

from __future__ import annotations

import os
import random
import socket
import ssl
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


LABEL = env("LABEL", "secsgem")
TLS_ENABLE = env("TLS_ENABLE", "false").lower() == "true"
PORT = env_int("PORT", 5000)
SSLKEYLOGFILE = env("SSLKEYLOGFILE", "")
_CERT_DIR = "/tmp/hsms_certs"


def log(message: str) -> None:
    print(f"[{LABEL}] {message}", flush=True)


# ---------------------------------------------------------------------------
# HSMS フレーム構築・解析
# ---------------------------------------------------------------------------

def _build_hsms_header(
    length: int,
    session_id: int,
    status_byte1: int,  # P/SType
    status_byte2: int,  # Function (0 for control)
    stype: int,         # 制御メッセージ SType (0 for data)
    sys_bytes: int,
) -> bytes:
    """HSMS メッセージヘッダ（10 バイト）を構築する。
    SEMI E37 の構造に従う。
    """
    return struct.pack(
        ">IHBBBBI",
        length,
        session_id,
        status_byte1,
        status_byte2,
        stype,
        0x00,  # header byte 9
        sys_bytes,
    )


def _select_req(sys_bytes: int = 1) -> bytes:
    hdr = struct.pack(">I", 10)  # length=10
    hdr += struct.pack(">H", 0xFFFF)  # session_id=0xFFFF
    hdr += bytes([0x00, 0x00, 0x01, 0x00])  # SType=0x01 (Select.req)
    hdr += struct.pack(">I", sys_bytes)
    return hdr


def _select_rsp(sys_bytes: int = 1) -> bytes:
    hdr = struct.pack(">I", 10)
    hdr += struct.pack(">H", 0xFFFF)
    hdr += bytes([0x00, 0x00, 0x02, 0x00])  # SType=0x02 (Select.rsp)
    hdr += struct.pack(">I", sys_bytes)
    return hdr


def _linktest_req(sys_bytes: int = 1) -> bytes:
    hdr = struct.pack(">I", 10)
    hdr += struct.pack(">H", 0xFFFF)
    hdr += bytes([0x00, 0x00, 0x05, 0x00])  # SType=0x05 (Linktest.req)
    hdr += struct.pack(">I", sys_bytes)
    return hdr


def _linktest_rsp(sys_bytes: int = 1) -> bytes:
    hdr = struct.pack(">I", 10)
    hdr += struct.pack(">H", 0xFFFF)
    hdr += bytes([0x00, 0x00, 0x06, 0x00])  # SType=0x06 (Linktest.rsp)
    hdr += struct.pack(">I", sys_bytes)
    return hdr


def _s1f1(session_id: int, sys_bytes: int) -> bytes:
    """S1F1 Are You There（Host→Equipment）"""
    # データなし（length=10、ヘッダのみ）
    hdr = struct.pack(">I", 10)
    hdr += struct.pack(">H", session_id)
    hdr += bytes([0x81, 0x01, 0x00, 0x00])  # P=0x80|0x01(S1), SType=0, F=1
    hdr += struct.pack(">I", sys_bytes)
    return hdr


def _s1f2(session_id: int, sys_bytes: int) -> bytes:
    """S1F2 On Line Data（Equipment→Host）モデル番号を含む最小実装"""
    # SECS-II: List{} (空レスポンス可)
    payload = b"\x01\x00"  # L[0] (空リスト)
    msg_len = 10 + len(payload)
    hdr = struct.pack(">I", msg_len)
    hdr += struct.pack(">H", session_id)
    hdr += bytes([0x01, 0x02, 0x00, 0x00])  # S1F2
    hdr += struct.pack(">I", sys_bytes)
    return hdr + payload


def _s6f11(session_id: int, sys_bytes: int, ceid: int, value: int) -> bytes:
    """S6F11 Event Report（Equipment→Host、プロセス変数通知）"""
    # 最小実装: L{CEID, RPTID, L{V}}
    payload = (
        b"\x01\x03"                                # L[3]
        + b"\xA5\x04" + struct.pack(">I", ceid)    # U4 CEID
        + b"\xA5\x04" + struct.pack(">I", 1)       # U4 RPTID=1
        + b"\x01\x01"                               # L[1] (report)
        + b"\x01\x01"                               # L[1] (variables)
        + b"\xA5\x04" + struct.pack(">I", value)   # U4 value
    )
    msg_len = 10 + len(payload)
    hdr = struct.pack(">I", msg_len)
    hdr += struct.pack(">H", session_id)
    hdr += bytes([0x06, 0x0B, 0x00, 0x00])  # S6F11
    hdr += struct.pack(">I", sys_bytes)
    return hdr + payload


def _recv_hsms(sock: socket.socket) -> bytes | None:
    """HSMS メッセージを受信する。接続切れは None。"""
    raw = b""
    while len(raw) < 4:
        chunk = sock.recv(4 - len(raw))
        if not chunk:
            return None
        raw += chunk
    length = struct.unpack(">I", raw)[0]
    if length < 10:
        return None
    # length は length フィールド自身を除く後続バイト数（SEMI E37）。
    # ここを `length - 4` にすると毎メッセージ4バイトが未読のまま
    # ソケットバッファに残り、次のメッセージの先頭とズレてストリーム
    # 全体のフレーミングが破綻する（Select 後の全メッセージが解析不能になる）。
    rest = b""
    while len(rest) < length:
        chunk = sock.recv(length - len(rest))
        if not chunk:
            return None
        rest += chunk
    return raw + rest


def _make_ssl_context_server() -> ssl.SSLContext | None:
    """TLS サーバコンテキストを生成する（自己署名証明書）。"""
    if not TLS_ENABLE:
        return None
    import subprocess
    os.makedirs(_CERT_DIR, exist_ok=True)
    key = f"{_CERT_DIR}/server.key"
    cert = f"{_CERT_DIR}/server.crt"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-keyout", key,
         "-out", cert, "-days", "365", "-nodes", "-subj", "/CN=hsms-equipment"],
        check=True, capture_output=True,
    )
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    if SSLKEYLOGFILE:
        # Python の ssl モジュールは SSLKEYLOGFILE 環境変数を自動では読まない。
        # keylog_filename を明示的に設定しないと鍵ログは一切書き出されない。
        os.makedirs(os.path.dirname(SSLKEYLOGFILE), exist_ok=True)
        ctx.keylog_filename = SSLKEYLOGFILE
    return ctx


def _make_ssl_context_client() -> ssl.SSLContext | None:
    if not TLS_ENABLE:
        return None
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    if SSLKEYLOGFILE:
        os.makedirs(os.path.dirname(SSLKEYLOGFILE), exist_ok=True)
        ctx.keylog_filename = SSLKEYLOGFILE
    return ctx


# ---------------------------------------------------------------------------
# サーバ（Equipment 役）
# ---------------------------------------------------------------------------

def _handle_host(conn: socket.socket, addr: tuple, session_id: int) -> None:
    log(f"host connected from {addr}")
    sys_bytes = 0
    selected = False
    try:
        conn.settimeout(60)
        while True:
            msg = _recv_hsms(conn)
            if msg is None:
                break
            if len(msg) < 10:
                break

            length_field = struct.unpack(">I", msg[:4])[0]
            hdr = msg[4:10]
            sess = struct.unpack(">H", msg[4:6])[0]
            sb1, sb2, stype, _ = hdr[2], hdr[3], hdr[4], hdr[5]
            sys_bytes_recv = struct.unpack(">I", msg[6:10])[0]

            if stype == 0x01:  # Select.req
                conn.sendall(_select_rsp(sys_bytes_recv))
                selected = True
                log(f"Select.req from {addr} -> Select.rsp sent (session established)")
            elif stype == 0x05:  # Linktest.req
                conn.sendall(_linktest_rsp(sys_bytes_recv))
                log(f"Linktest.req from {addr} -> Linktest.rsp sent")
            elif stype == 0x00 and selected:
                # SECS-II データメッセージ
                stream = sb1 & 0x7F
                func = sb2
                log(f"S{stream}F{func} from {addr} (len={length_field})")
                if stream == 1 and func == 1:
                    # S1F1 に S1F2 で応答
                    conn.sendall(_s1f2(session_id, sys_bytes_recv))
                    log(f"S1F1 -> S1F2 sent")
                else:
                    log(f"unhandled S{stream}F{func}")
            elif stype == 0x09:  # Separate.req
                log(f"Separate.req from {addr}, closing")
                break
    except (OSError, socket.timeout):
        pass
    finally:
        conn.close()
        log(f"disconnected: {addr}")


def run_server() -> None:
    ssl_ctx = _make_ssl_context_server()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(8)
    log(f"HSMS Equipment server on 0.0.0.0:{PORT} (tls={TLS_ENABLE})")

    session_counter = 0
    while True:
        conn, addr = srv.accept()
        if ssl_ctx:
            try:
                conn = ssl_ctx.wrap_socket(conn, server_side=True)
            except ssl.SSLError as exc:
                log(f"TLS handshake failed: {exc}")
                conn.close()
                continue
        session_counter += 1
        t = threading.Thread(target=_handle_host, args=(conn, addr, session_counter), daemon=True)
        t.start()


# ---------------------------------------------------------------------------
# クライアント（Host 役）
# ---------------------------------------------------------------------------

def run_client() -> None:
    target = env("TARGET")
    if not target:
        log("TARGET が未設定です（MODE=client では接続先IPが必須）")
        sys.exit(1)

    interval = env_float("INTERVAL", 10)
    ssl_ctx = _make_ssl_context_client()

    log(f"connecting to {target}:{PORT} (tls={TLS_ENABLE})")
    sys_bytes = 0

    while True:
        try:
            raw_sock = socket.create_connection((target, PORT), timeout=15)
            if ssl_ctx:
                sock = ssl_ctx.wrap_socket(raw_sock, server_hostname=target)
            else:
                sock = raw_sock

            log(f"connected to {target}:{PORT}")

            # Select.req でセッション確立
            sys_bytes += 1
            sock.sendall(_select_req(sys_bytes))
            resp = _recv_hsms(sock)
            if resp is None or len(resp) < 10 or resp[8] != 0x02:
                log("Select.rsp not received, closing")
                sock.close()
                time.sleep(interval)
                continue
            log("HSMS session selected (active)")

            session_id = 0x0001
            while True:
                # S1F1 Are You There
                sys_bytes += 1
                sock.sendall(_s1f1(session_id, sys_bytes))
                resp = _recv_hsms(sock)
                if resp is None:
                    break
                if len(resp) >= 10:
                    sb1, sb2 = resp[6], resp[7]
                    log(f"recv S{sb1 & 0x7F}F{sb2} (len={len(resp)})")

                # Linktest
                sys_bytes += 1
                sock.sendall(_linktest_req(sys_bytes))
                resp = _recv_hsms(sock)
                if resp is None:
                    break
                log("Linktest.rsp received")

                time.sleep(interval)

            sock.close()

        except (OSError, socket.timeout, ssl.SSLError) as exc:
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

#!/usr/bin/env python3
"""EtherNet/IP (CIP) のアダプタ（PLC役）とスキャナ（上位監視役）。

サイバーレンジの資産として置くための最小実装。環境変数で役割と接続先を
変えられるようにしてあり、同じイメージを複数の分野・複数の資産で使い回す
(使い方は docs/protocol-assets.md)。

環境変数:
    MODE      adapter | scanner    （既定: adapter。server/client も可）
    PORT      待ち受け/接続先ポート（既定: 44818）
    TARGET    接続先IP（scanner時のみ必須）
    INTERVAL  ポーリング間隔[秒]   （既定: 5）
    PRODUCT   アダプタが名乗る製品名（既定: Amenonuboco Range Controller）
    CONTEXT   送信者コンテキスト（8バイトまで。既定: 空＝ゼロ埋め）
    LABEL     ログに出す識別名     （既定: enip）

**実装方針**：フレームをライブラリに頼らず生のバイト列で組み立てる。
EtherNet/IPのカプセル化ヘッダは24バイト固定で、必要なコマンド
（RegisterSession / SendRRData）とCIPサービス（Get_Attribute_All /
Set_Attribute_Single）に限れば短く書ける。**送信するバイト列を完全に
把握できる**ことは、構造化パイプラインが何を解析しているかを検証する上でも
利点になる。

`CONTEXT` は送信者コンテキスト（EtherNet/IPヘッダの8バイト任意領域）に
そのまま載る。要求と応答を対応づけるための欄で、**中身は検査されない**——
攻撃シナリオで目印を仕込む場所として使える。
"""

from __future__ import annotations

import os
import random
import socket
import struct
import sys
import time
import ssl
import subprocess

# --- カプセル化ヘッダ（24バイト固定） ----------------------------------------
#   command(2,LE) | length(2,LE) | session handle(4,LE) | status(4,LE)
#   | sender context(8) | options(4,LE)

CMD_LIST_IDENTITY = 0x0063
CMD_REGISTER_SESSION = 0x0065
CMD_UNREGISTER_SESSION = 0x0066
CMD_SEND_RR_DATA = 0x006F

# CIPサービスコード。応答では最上位ビットが立つ（0x01 -> 0x81）。
CIP_GET_ATTRIBUTE_ALL = 0x01
CIP_SET_ATTRIBUTE_SINGLE = 0x10
CIP_GET_ATTRIBUTE_SINGLE = 0x0E

# CPF（共通パケット形式）アイテム種別
CPF_NULL_ADDRESS = 0x0000
CPF_UNCONNECTED_DATA = 0x00B2

_HEADER = struct.Struct("<HHII8sI")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name) or default)
    except ValueError:
        return default


LABEL = env("LABEL", "enip")
PORT = env_int("PORT", 44818)
CONTEXT = env("CONTEXT", "").encode("utf-8")[:8].ljust(8, b"\x00")
TLS_ENABLE = env("TLS_ENABLE", "false").lower() == "true"
SSLKEYLOGFILE = env("SSLKEYLOGFILE", "")
if SSLKEYLOGFILE:
    os.makedirs(os.path.dirname(SSLKEYLOGFILE), exist_ok=True)

def get_ssl_context(is_server: bool) -> ssl.SSLContext:
    if is_server:
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        if not os.path.exists("server.crt"):
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-keyout", "server.key",
                "-out", "server.crt", "-days", "365", "-nodes", "-subj", "/CN=enip"
            ], check=True, capture_output=True)
        ctx.load_cert_chain(certfile="server.crt", keyfile="server.key")
    else:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    if SSLKEYLOGFILE:
        # Python の ssl モジュールは SSLKEYLOGFILE 環境変数を自動では読まない
        # （curl/OpenSSL CLI やブラウザとは異なる）。ハンドシェイク前に
        # SSLContext.keylog_filename を明示的に設定しないと鍵ログは一切
        # 書き出されない（演習用暗号鍵注入アーキテクチャ、決定事項#160）。
        ctx.keylog_filename = SSLKEYLOGFILE

    return ctx


def log(message: str) -> None:
    print(f"[{LABEL}] {message}", flush=True)


def encap(command: int, session: int, payload: bytes, status: int = 0) -> bytes:
    return _HEADER.pack(command, len(payload), session, status, CONTEXT, 0) + payload


def parse_encap(raw: bytes) -> tuple[int, int, int, bytes]:
    command, length, session, status, _context, _options = _HEADER.unpack(raw[:24])
    return command, session, status, raw[24 : 24 + length]


def send_rr_data(cip: bytes) -> bytes:
    """SendRRData のペイロード（インタフェースハンドル＋タイムアウト＋CPF）。"""
    return (
        struct.pack("<IH", 0, 5)
        + struct.pack("<H", 2)  # CPFアイテム数
        + struct.pack("<HH", CPF_NULL_ADDRESS, 0)
        + struct.pack("<HH", CPF_UNCONNECTED_DATA, len(cip))
        + cip
    )


def extract_cip(payload: bytes) -> bytes:
    """SendRRDataのペイロードから、非接続データアイテムの中身を取り出す。"""
    offset = 6
    (count,) = struct.unpack_from("<H", payload, offset)
    offset += 2
    for _ in range(count):
        item_type, item_len = struct.unpack_from("<HH", payload, offset)
        offset += 4
        if item_type == CPF_UNCONNECTED_DATA:
            return payload[offset : offset + item_len]
        offset += item_len
    return b""


def cip_request(service: int, class_id: int, instance: int, data: bytes = b"") -> bytes:
    """論理セグメント（8bitクラス・8bitインスタンス）でパスを組む。"""
    path = struct.pack("<BBBB", 0x20, class_id, 0x24, instance)
    return bytes([service, len(path) // 2]) + path + data


def cip_response(service: int, status: int, data: bytes = b"") -> bytes:
    return bytes([service | 0x80, 0x00, status, 0x00]) + data


# --- ストリームからのフレーム切り出し ----------------------------------------


def read_message(sock: socket.socket, buffer: bytearray) -> bytes | None:
    """TCPはフレーム境界を保たないため、ヘッダの長さ欄を見て切り出す。"""
    while True:
        if len(buffer) >= 24:
            (length,) = struct.unpack_from("<H", buffer, 2)
            total = 24 + length
            if len(buffer) >= total:
                message = bytes(buffer[:total])
                del buffer[:total]
                return message
        chunk = sock.recv(4096)
        if not chunk:
            return None
        buffer.extend(chunk)


# --- 役割 --------------------------------------------------------------------


def _identity_payload(product: str) -> bytes:
    """Identityオブジェクト（クラス0x01）の全属性。機器が名乗る素性そのもの。"""
    name = product.encode("utf-8")[:32]
    return (
        struct.pack("<HHH", 0x004D, 0x000C, 0x0001)  # ベンダID, 機器種別, 製品コード
        + bytes([1, 0])  # リビジョン（メジャー・マイナー）
        + struct.pack("<HI", 0x0030, 0x1A2B3C4D)  # 状態, シリアル番号
        + bytes([len(name)])
        + name
    )


def run_adapter() -> None:
    product = env("PRODUCT", "Amenonuboco Range Controller")
    # Assemblyオブジェクト（クラス0x04）が持つ「現在値」。スキャナが読み書きする。
    assembly_value = random.randint(0, 4095)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", PORT))
    listener.listen(5)
    
    if TLS_ENABLE:
        ctx = get_ssl_context(is_server=True)
        listener = ctx.wrap_socket(listener, server_side=True)
        log(f"EtherNet/IP (CIP Security TLS) adapter listening on 0.0.0.0:{PORT} ('{product}')")
    else:
        log(f"EtherNet/IP adapter listening on 0.0.0.0:{PORT} ('{product}')")

    while True:
        conn, addr = listener.accept()
        log(f"scanner connected from {addr[0]}")
        session = random.randint(0x00000001, 0x7FFFFFFF)
        buffer = bytearray()
        try:
            while True:
                message = read_message(conn, buffer)
                if message is None:
                    break
                command, _session, _status, payload = parse_encap(message)

                if command == CMD_REGISTER_SESSION:
                    log(f"RegisterSession -> handle 0x{session:08x}")
                    conn.sendall(
                        encap(CMD_REGISTER_SESSION, session, struct.pack("<HH", 1, 0))
                    )
                elif command == CMD_LIST_IDENTITY:
                    log("ListIdentity")
                    conn.sendall(encap(CMD_LIST_IDENTITY, session, b"\x00\x00"))
                elif command == CMD_SEND_RR_DATA:
                    cip = extract_cip(payload)
                    service = cip[0] if cip else 0
                    if service == CIP_GET_ATTRIBUTE_ALL:
                        log("CIP Get_Attribute_All (Identity)")
                        reply = cip_response(service, 0x00, _identity_payload(product))
                    elif service == CIP_GET_ATTRIBUTE_SINGLE:
                        assembly_value = random.randint(0, 4095)
                        log(f"CIP Get_Attribute_Single -> {assembly_value}")
                        reply = cip_response(
                            service, 0x00, struct.pack("<H", assembly_value)
                        )
                    elif service == CIP_SET_ATTRIBUTE_SINGLE:
                        (assembly_value,) = struct.unpack_from("<H", cip, len(cip) - 2)
                        log(f"CIP Set_Attribute_Single <- {assembly_value}")
                        reply = cip_response(service, 0x00)
                    else:
                        log(f"unsupported CIP service 0x{service:02x}")
                        reply = cip_response(service, 0x08)  # Service not supported
                    conn.sendall(encap(CMD_SEND_RR_DATA, session, send_rr_data(reply)))
                elif command == CMD_UNREGISTER_SESSION:
                    log("UnRegisterSession")
                    break
                else:
                    log(f"unhandled encapsulation command 0x{command:04x}")
        except Exception as exc:  # noqa: BLE001 - レンジ資産は落とさず回し続ける
            log(f"session error: {exc}")
        finally:
            conn.close()
            log("scanner disconnected")


def run_scanner() -> None:
    target = env("TARGET")
    if not target:
        log("TARGET が未設定です（MODE=scanner では接続先IPが必須）")
        sys.exit(1)

    interval = env_int("INTERVAL", 5)
    log(f"polling {target}:{PORT} every {interval}s")

    polls = 0
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        if TLS_ENABLE:
            ctx = get_ssl_context(is_server=False)
            sock = ctx.wrap_socket(sock, server_hostname=target)
        try:
            sock.connect((target, PORT))
        except OSError as exc:
            # アダプタ側の起動待ちで最初の数回は失敗しうる。異常終了させず、
            # 次の周期で再試行する（起動順序に依存しない器にするため）。
            log(f"connect failed to {target}:{PORT} ({exc}), retrying")
            sock.close()
            time.sleep(interval)
            continue

        buffer = bytearray()
        try:
            sock.sendall(encap(CMD_REGISTER_SESSION, 0, struct.pack("<HH", 1, 0)))
            message = read_message(sock, buffer)
            if message is None:
                raise ConnectionError("no RegisterSession response")
            _command, session, _status, _payload = parse_encap(message)
            log(f"session registered (handle 0x{session:08x})")

            while True:
                polls += 1
                if polls % 5 == 1:
                    # 起動直後と定期的に機器の素性を確認する（実機の
                    # スキャナが接続時に必ず行う手続き）。
                    log("sending CIP Get_Attribute_All (Identity)")
                    request = cip_request(CIP_GET_ATTRIBUTE_ALL, 0x01, 1)
                elif polls % 5 == 0:
                    # 5回に1回は書き込み。読み取りとは別のサービスコードに
                    # なるため、構造化した時に「何をされたか」の区別が現れる。
                    value = random.randint(0, 4095)
                    log(f"sending CIP Set_Attribute_Single = {value}")
                    request = cip_request(
                        CIP_SET_ATTRIBUTE_SINGLE, 0x04, 100, struct.pack("<H", value)
                    )
                else:
                    log("sending CIP Get_Attribute_Single (Assembly)")
                    request = cip_request(CIP_GET_ATTRIBUTE_SINGLE, 0x04, 100)

                sock.sendall(encap(CMD_SEND_RR_DATA, session, send_rr_data(request)))
                message = read_message(sock, buffer)
                if message is None:
                    log("adapter closed the connection, reconnecting")
                    break
                _command, _session, _status, payload = parse_encap(message)
                cip = extract_cip(payload)
                status = cip[2] if len(cip) > 2 else 0xFF
                log(f"response: service 0x{cip[0]:02x}, general status 0x{status:02x}")
                time.sleep(interval)
        except Exception as exc:  # noqa: BLE001
            log(f"session error: {exc}, reconnecting")
        finally:
            sock.close()
            time.sleep(interval)


def main() -> None:
    mode = env("MODE", "adapter").lower()
    if mode in ("adapter", "server"):
        run_adapter()
    elif mode in ("scanner", "client"):
        run_scanner()
    else:
        log(f"未知の MODE '{mode}'（adapter または scanner を指定してください）")
        sys.exit(1)


if __name__ == "__main__":
    main()

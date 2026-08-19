#!/usr/bin/env python3
"""SIP の UAS（レジストラ／PBX役）と UAC（IP電話・ソフトフォン役）。

サイバーレンジの資産として置くための最小実装。環境変数で役割と接続先を
変えられるようにしてあり、同じイメージを複数の分野・複数の資産で使い回す
(使い方は docs/protocol-assets.md)。

環境変数:
    MODE      uas | uac            （既定: uas。server/client も可）
    PORT      待ち受け/接続先ポート（既定: 5060）
    TARGET    接続先IP（uac時のみ必須）
    INTERVAL  発呼間隔[秒]         （既定: 10）
    DOMAIN    SIPドメイン          （既定: range.invalid）
    USER      自分のユーザ名       （既定: uas=pbx / uac=phone1）
    PEER_USER 相手のユーザ名       （既定: pbx）
    LABEL     ログに出す識別名     （既定: sip）

**実装方針**：外部ライブラリを使わない。SIPはHTTPに似たテキストプロトコルで
あり、REGISTER と 1本の呼（INVITE → 180 → 200 → ACK → BYE → 200）に限れば、
ヘッダを組み立てるだけで表現できる。**送信するバイト列を完全に把握できる**
ことは、構造化パイプラインが何を解析しているかを検証する上でも利点になる。

**認証は行わない**（レジストラは REGISTER に無条件で 200 OK を返す）。
認証を要求しないSIPサービスが外部から到達可能、という構図自体が通信分野の
器で描きたい状態であり、また平文であることが観測の前提でもある。
"""

from __future__ import annotations

import os
import random
import socket
import sys
import time

# SIPの行区切りはCRLF。LFだけにするとtsharkもUAも解釈できない。
_CRLF = "\r\n"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name) or default)
    except ValueError:
        return default


LABEL = env("LABEL", "sip")
PORT = env_int("PORT", 5060)
DOMAIN = env("DOMAIN", "range.invalid")


def log(message: str) -> None:
    print(f"[{LABEL}] {message}", flush=True)


def _token(length: int = 10) -> str:
    return "".join(random.choice("0123456789abcdef") for _ in range(length))


def _build(start_line: str, headers: list[tuple[str, str]], body: str = "") -> bytes:
    lines = [start_line]
    lines += [f"{name}: {value}" for name, value in headers]
    lines.append(f"Content-Length: {len(body)}")
    return (_CRLF.join(lines) + _CRLF + _CRLF + body).encode("utf-8")


def _parse(data: bytes) -> tuple[str, dict[str, str]]:
    """(開始行, ヘッダ辞書) を返す。同名ヘッダは最初の1つだけを採る。"""
    text = data.decode("utf-8", errors="replace")
    head = text.split(_CRLF + _CRLF, 1)[0]
    lines = head.split(_CRLF)
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            name, _, value = line.partition(":")
            headers.setdefault(name.strip().lower(), value.strip())
    return (lines[0] if lines else ""), headers


def _sdp(host: str, port: int) -> str:
    """最小のSDP（呼のメディア記述）。実際のRTPは流さない。"""
    return _CRLF.join(
        [
            "v=0",
            f"o=- {random.randint(1000, 9999)} 1 IN IP4 {host}",
            "s=Amenonuboco Range Session",
            f"c=IN IP4 {host}",
            "t=0 0",
            f"m=audio {port} RTP/AVP 0 8",
            "a=rtpmap:0 PCMU/8000",
            "a=rtpmap:8 PCMA/8000",
            "",
        ]
    )


# --- 役割 --------------------------------------------------------------------


def _response(status: str, request_headers: dict[str, str], own_tag: str, body: str = ""):
    headers = [
        ("Via", request_headers.get("via", "")),
        ("From", request_headers.get("from", "")),
        ("To", f"{request_headers.get('to', '')};tag={own_tag}"),
        ("Call-ID", request_headers.get("call-id", "")),
        ("CSeq", request_headers.get("cseq", "")),
        ("Server", "Amenonuboco-Range/1.0"),
    ]
    if body:
        headers.append(("Content-Type", "application/sdp"))
    return _build(f"SIP/2.0 {status}", headers, body)


def run_uas() -> None:
    user = env("USER", "pbx")
    own_tag = _token(8)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", PORT))
    log(f"SIP UAS listening on 0.0.0.0:{PORT}/udp (sip:{user}@{DOMAIN})")

    while True:
        try:
            data, addr = sock.recvfrom(4096)
        except Exception as exc:  # noqa: BLE001 - レンジ資産は落とさず回し続ける
            log(f"recv error: {exc}")
            continue

        start_line, headers = _parse(data)
        method = start_line.split(" ", 1)[0].upper()

        if method == "REGISTER":
            log(f"REGISTER from {addr[0]} ({headers.get('from', '?')})")
            sock.sendto(_response("200 OK", headers, own_tag), addr)
        elif method == "INVITE":
            log(f"INVITE from {addr[0]} -> 100 / 180 / 200 with SDP")
            sock.sendto(_response("100 Trying", headers, own_tag), addr)
            sock.sendto(_response("180 Ringing", headers, own_tag), addr)
            # 呼び出し中の間があるほうが実際の呼に近く、構造化した時にも
            # 暫定応答と最終応答が別のパケットとして並ぶ。
            time.sleep(0.5)
            sock.sendto(
                _response("200 OK", headers, own_tag, _sdp("0.0.0.0", 40000)), addr
            )
        elif method == "ACK":
            log(f"ACK from {addr[0]} (call established)")
        elif method == "BYE":
            log(f"BYE from {addr[0]} -> 200 OK (call ended)")
            sock.sendto(_response("200 OK", headers, own_tag), addr)
        elif method == "OPTIONS":
            sock.sendto(_response("200 OK", headers, own_tag), addr)
        elif start_line.startswith("SIP/2.0"):
            pass  # 応答は無視（このUASは発呼しない）
        else:
            log(f"unhandled method '{method}' from {addr[0]}")
            sock.sendto(_response("405 Method Not Allowed", headers, own_tag), addr)


def run_uac() -> None:
    target = env("TARGET")
    if not target:
        log("TARGET が未設定です（MODE=uac では接続先IPが必須）")
        sys.exit(1)

    user = env("USER", "phone1")
    peer_user = env("PEER_USER", "pbx")
    interval = env_int("INTERVAL", 10)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    sock.settimeout(3)
    own_ip = sock.getsockname()[0]
    # bind時点では 0.0.0.0 なので、宛先への経路から自分のIPを引く。
    # Via/Contact に 0.0.0.0 を書くと応答の戻り先が壊れる。
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect((target, PORT))
        own_ip = probe.getsockname()[0]
    finally:
        probe.close()

    log(f"calling sip:{peer_user}@{DOMAIN} via {target}:{PORT} every {interval}s")

    def base_headers(method: str, call_id: str, cseq: int, from_tag: str):
        return [
            ("Via", f"SIP/2.0/UDP {own_ip}:{PORT};branch=z9hG4bK{_token()}"),
            ("Max-Forwards", "70"),
            ("From", f"<sip:{user}@{DOMAIN}>;tag={from_tag}"),
            ("To", f"<sip:{peer_user}@{DOMAIN}>"),
            ("Call-ID", call_id),
            ("CSeq", f"{cseq} {method}"),
            ("Contact", f"<sip:{user}@{own_ip}:{PORT}>"),
            ("User-Agent", "Amenonuboco-Range/1.0"),
        ]

    def drain(label: str, seconds: float = 2.0) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                data, _addr = sock.recvfrom(4096)
            except socket.timeout:
                return
            start_line, _headers = _parse(data)
            log(f"{label}: {start_line}")

    while True:
        try:
            call_id = f"{_token(12)}@{own_ip}"
            from_tag = _token(8)

            # 登録（電話機が起動時に必ず行う手続き）
            sock.sendto(
                _build(
                    f"REGISTER sip:{DOMAIN} SIP/2.0",
                    base_headers("REGISTER", call_id, 1, from_tag)
                    + [("Expires", "3600")],
                ),
                (target, PORT),
            )
            log("sent REGISTER")
            drain("register response")

            # 発呼
            call_id = f"{_token(12)}@{own_ip}"
            body = _sdp(own_ip, 40000)
            sock.sendto(
                _build(
                    f"INVITE sip:{peer_user}@{DOMAIN} SIP/2.0",
                    base_headers("INVITE", call_id, 2, from_tag)
                    + [("Content-Type", "application/sdp")],
                    body,
                ),
                (target, PORT),
            )
            log("sent INVITE")
            drain("invite response", 3.0)

            sock.sendto(
                _build(
                    f"ACK sip:{peer_user}@{DOMAIN} SIP/2.0",
                    base_headers("ACK", call_id, 2, from_tag),
                ),
                (target, PORT),
            )
            log("sent ACK (call established)")

            # 通話中に相当する間
            time.sleep(2)

            sock.sendto(
                _build(
                    f"BYE sip:{peer_user}@{DOMAIN} SIP/2.0",
                    base_headers("BYE", call_id, 3, from_tag),
                ),
                (target, PORT),
            )
            log("sent BYE")
            drain("bye response")
        except Exception as exc:  # noqa: BLE001 - レンジ資産は落とさず回し続ける
            # UAS側の起動待ちで最初の数回は応答が無いことがある。異常終了させず、
            # 次の周期で再試行する（起動順序に依存しない器にするため）。
            log(f"unexpected error: {exc}")
        time.sleep(interval)


def main() -> None:
    mode = env("MODE", "uas").lower()
    if mode in ("uas", "server", "registrar"):
        run_uas()
    elif mode in ("uac", "client", "phone"):
        run_uac()
    else:
        log(f"未知の MODE '{mode}'（uas または uac を指定してください）")
        sys.exit(1)


if __name__ == "__main__":
    main()

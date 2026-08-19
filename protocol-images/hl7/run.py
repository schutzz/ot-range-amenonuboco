#!/usr/bin/env python3
"""HL7 v2 over MLLP の受信側（電子カルテ・部門システム役）と送信側（モダリティ役）。

サイバーレンジの資産として置くための最小実装。環境変数で役割と接続先を
変えられるようにしてあり、同じイメージを複数の分野・複数の資産で使い回す
(使い方は docs/protocol-assets.md)。

環境変数:
    MODE      receiver | sender    （既定: receiver。server/client も可）
    PORT      待ち受け/接続先ポート（既定: 2575）
    TARGET    接続先IP（sender時のみ必須）
    INTERVAL  送信間隔[秒]         （既定: 5）
    APP       自システムのアプリ名 （既定: receiver=EMR / sender=MODALITY）
    FACILITY  施設名               （既定: RANGE_HOSPITAL）
    LABEL     ログに出す識別名     （既定: hl7）

**実装方針**：外部ライブラリを使わない。MLLPは「開始バイト 0x0B ＋ 本文 ＋
終了バイト 0x1C 0x0D」というだけのフレーミングであり、HL7 v2 自体も
区切り文字で並べたテキストである。ライブラリを挟むより、**送信する
バイト列を完全に把握できる**方が、構造化パイプラインが何を解析しているかを
検証する上で有利になる。

**扱うデータは完全な合成データである。** 患者名・患者IDは実在しないことが
一目で分かる値（`SYNTHETIC^RANGE-PATIENT` / `RANGE-nnnn`）に固定してある。
医療分野の器は「患者情報がネットワークを平文で流れる」という構図の再現が
目的であって、それらしい中身の捏造ではない。
"""

from __future__ import annotations

import os
import random
import socket
import sys
import time
from datetime import datetime, timezone

# MLLP のフレーミング。この3バイトだけがHL7 v2をTCP上で区切っている。
_SB = b"\x0b"  # start block
_EB = b"\x1c"  # end block
_CR = b"\x0d"  # carriage return

# HL7 v2 のセグメント区切りも CR（改行ではない）。ここを \n にすると
# 受信側もtsharkも1セグメントの塊としてしか読めなくなる。
_SEG = "\r"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name) or default)
    except ValueError:
        return default


LABEL = env("LABEL", "hl7")
PORT = env_int("PORT", 2575)
FACILITY = env("FACILITY", "RANGE_HOSPITAL")


def log(message: str) -> None:
    print(f"[{LABEL}] {message}", flush=True)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _wrap(message: str) -> bytes:
    return _SB + message.encode("utf-8") + _EB + _CR


def _unwrap(frame: bytes) -> str:
    return frame.strip(_SB + _EB + _CR).decode("utf-8", errors="replace")


# --- メッセージ組み立て ------------------------------------------------------


def _msh(sending_app: str, receiving_app: str, message_type: str, control_id: str) -> str:
    # MSH-1 が区切り文字 '|'、MSH-2 がエスケープ文字群 '^~\&' という決まり。
    return (
        f"MSH|^~\\&|{sending_app}|{FACILITY}|{receiving_app}|{FACILITY}|"
        f"{_timestamp()}||{message_type}|{control_id}|P|2.5"
    )


def adt_a01(sending_app: str, receiving_app: str, control_id: str, patient_id: str) -> str:
    """ADT^A01（入院登録）。患者の識別情報がそのまま流れる代表例。"""
    return _SEG.join(
        [
            _msh(sending_app, receiving_app, "ADT^A01", control_id),
            f"EVN|A01|{_timestamp()}",
            f"PID|1||{patient_id}^^^{FACILITY}^MR||SYNTHETIC^RANGE-PATIENT||"
            "19700101|M|||1 Range Street^^Rangeville^XX^00000",
            "PV1|1|I|WARD1^101^A||||||||||||||||INPATIENT",
        ]
    )


def oru_r01(
    sending_app: str, receiving_app: str, control_id: str, patient_id: str
) -> str:
    """ORU^R01（検査結果報告）。数値の観測結果を伴う。"""
    return _SEG.join(
        [
            _msh(sending_app, receiving_app, "ORU^R01", control_id),
            f"PID|1||{patient_id}^^^{FACILITY}^MR||SYNTHETIC^RANGE-PATIENT||19700101|M",
            f"OBR|1||{control_id}|CBC^COMPLETE BLOOD COUNT^L|||{_timestamp()}",
            f"OBX|1|NM|HR^HEART RATE^L||{random.randint(55, 110)}|bpm|60-100||||F",
            f"OBX|2|NM|SPO2^OXYGEN SATURATION^L||{random.randint(92, 100)}|%|95-100||||F",
        ]
    )


def ack(sending_app: str, receiving_app: str, control_id: str, code: str = "AA") -> str:
    """ACK（受理応答）。MSA-1 の AA/AE/AR が受理・エラー・拒否を表す。"""
    return _SEG.join(
        [
            _msh(sending_app, receiving_app, "ACK", f"ACK{control_id}"),
            f"MSA|{code}|{control_id}",
        ]
    )


# --- ストリームからのフレーム切り出し ----------------------------------------


def read_frame(sock: socket.socket, buffer: bytearray) -> bytes | None:
    """TCPはフレーム境界を保たないため、終了バイト列を探して切り出す。"""
    terminator = _EB + _CR
    while True:
        end = buffer.find(terminator)
        if end >= 0:
            frame = bytes(buffer[: end + 2])
            del buffer[: end + 2]
            return frame
        chunk = sock.recv(4096)
        if not chunk:
            return None
        buffer.extend(chunk)


# --- 役割 --------------------------------------------------------------------


def run_receiver() -> None:
    app = env("APP", "EMR")

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", PORT))
    listener.listen(5)
    log(f"HL7 MLLP receiver listening on 0.0.0.0:{PORT} (app={app})")

    while True:
        conn, addr = listener.accept()
        log(f"sender connected from {addr[0]}")
        buffer = bytearray()
        try:
            while True:
                frame = read_frame(conn, buffer)
                if frame is None:
                    break
                message = _unwrap(frame)
                fields = message.split(_SEG)[0].split("|")
                message_type = fields[8] if len(fields) > 8 else "?"
                control_id = fields[9] if len(fields) > 9 else "?"
                peer_app = fields[2] if len(fields) > 2 else "?"
                log(f"received {message_type} (control id {control_id}) from {peer_app}")
                conn.sendall(_wrap(ack(app, peer_app, control_id)))
        except Exception as exc:  # noqa: BLE001 - レンジ資産は落とさず回し続ける
            log(f"session error: {exc}")
        finally:
            conn.close()
            log("sender disconnected")


def run_sender() -> None:
    target = env("TARGET")
    if not target:
        log("TARGET が未設定です（MODE=sender では接続先IPが必須）")
        sys.exit(1)

    app = env("APP", "MODALITY")
    peer_app = env("PEER_APP", "EMR")
    interval = env_int("INTERVAL", 5)
    log(f"sending to {target}:{PORT} every {interval}s (app={app} -> {peer_app})")

    counter = 0
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        try:
            sock.connect((target, PORT))
        except OSError as exc:
            # 受信側の起動待ちで最初の数回は失敗しうる。異常終了させず、
            # 次の周期で再試行する（起動順序に依存しない器にするため）。
            log(f"connect failed to {target}:{PORT} ({exc}), retrying")
            sock.close()
            time.sleep(interval)
            continue

        buffer = bytearray()
        try:
            while True:
                counter += 1
                control_id = f"MSG{counter:06d}"
                patient_id = f"RANGE-{random.randint(1000, 9999)}"
                # 入院登録と検査結果を交互に送る。メッセージ種別が違えば
                # 構造化した時のセグメント構成も変わり、「何が流れたか」の
                # 区別が現れる。
                if counter % 2 == 1:
                    message = adt_a01(app, peer_app, control_id, patient_id)
                    log(f"sending ADT^A01 ({control_id}, patient {patient_id})")
                else:
                    message = oru_r01(app, peer_app, control_id, patient_id)
                    log(f"sending ORU^R01 ({control_id}, patient {patient_id})")
                sock.sendall(_wrap(message))

                frame = read_frame(sock, buffer)
                if frame is None:
                    log("receiver closed the connection, reconnecting")
                    break
                reply = _unwrap(frame).split(_SEG)
                log(f"ack: {reply[-1] if reply else '?'}")
                time.sleep(interval)
        except Exception as exc:  # noqa: BLE001
            log(f"session error: {exc}, reconnecting")
        finally:
            sock.close()
            time.sleep(interval)


def main() -> None:
    mode = env("MODE", "receiver").lower()
    if mode in ("receiver", "server"):
        run_receiver()
    elif mode in ("sender", "client"):
        run_sender()
    else:
        log(f"未知の MODE '{mode}'（receiver または sender を指定してください）")
        sys.exit(1)


if __name__ == "__main__":
    main()

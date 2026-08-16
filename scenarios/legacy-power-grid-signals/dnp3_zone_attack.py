#!/usr/bin/env python3
"""dnp3_zone_attack.py — Signal1(ゾーン逸脱)の陽性テスト用攻撃スクリプト。

前身`ot-ids-verum`の`Phase-ex/dnp3_frame.py`(DNP3フレーム生成)と
`Phase-ex/test_7_positive_zone.py`(陽性テスト、許可リスト外のホストから送信)
を、Amenonuboco環境向けに1ファイルへ統合したもの。標準ライブラリのみで動く
(実行対象のコンテナに追加のpip installを要求しない、攻撃者ノードへ配布する
シナリオ資産として持ち運びやすくするため)。

送信元がこのスクリプトを実行したホスト自身のIPになる(ソケットのソースIPは
OSが決める)ため、許可リストに無いホスト(例: sub_a_ied_02)から実行すれば
ゾーン逸脱の陽性テストになる。

責務はDNP3フレームの送信のみに限定する。正解ラベルの記録は本スクリプトでは
行わない(【訂正】Phase5実装時に発見: 攻撃者コンテナは`sub_a_l2_lan`のみに
接続しており`cc_lan`上のElasticsearchへ名前解決できない、というネットワーク
制約に実際に遭遇した際、そもそも**攻撃者コンテナ自身が正解ラベルをESへ
書き込む設計は、前身が排除しようとした「OOB自己申告」と本質的に同じ構図
になってしまう**ことに気づいた。正解ラベルは「演習を実行した側(オペレータ/
評価者)が独立に記録するもの」であるべきで、攻撃者ノード自身の自己申告に
してはならない。記録は`record_ground_truth.py`へ分離し、cc_lanに接続された
評価用ホストから実行する、罠ログ#017参照)。
"""

from __future__ import annotations

import argparse
import socket
import sys


def crc_dnp(data: bytes) -> bytes:
    """CRC-DNP (poly=0xA6BC, reversed, init=0x0000, xorout=0xFFFF)。
    前身`Phase-ex/dnp3_frame.py`のCRC実装をそのまま移植。
    """
    crc = 0x0000
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA6BC if (crc & 1) else (crc >> 1)
    crc ^= 0xFFFF
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def _with_crc_blocks(data: bytes) -> bytes:
    """DNP3はユーザデータを16バイトごとのブロックに区切り、各ブロックにCRCを付与する。"""
    out = b""
    for i in range(0, len(data), 16):
        chunk = data[i : i + 16]
        out += chunk + crc_dnp(chunk)
    return out


def build_dnp3_frame(function_code: int, dest: int = 1, src: int = 1024) -> bytes:
    """function_code: DNP3アプリケーション層ファンクションコード(1=READ等)。"""
    transport = 0xC0
    app_ctrl = 0xC0
    user_data = bytes([transport, app_ctrl, function_code])
    user_data_with_crc = _with_crc_blocks(user_data)

    ctrl = 0xC4  # DIR + PRM + FUNC=UNCONFIRMED_USER_DATA
    length = 5 + len(user_data)
    dl_body = bytes([length, ctrl]) + dest.to_bytes(2, "little") + src.to_bytes(2, "little")
    header = b"\x05\x64" + dl_body
    header_crc = crc_dnp(header)

    return header + header_crc + user_data_with_crc


def send_dnp3(target_ip: str, target_port: int, function_code: int) -> str:
    payload = build_dnp3_frame(function_code=function_code)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3.0)
    try:
        s.connect((target_ip, target_port))
        my_src_ip = s.getsockname()[0]
        s.sendall(payload)
    finally:
        s.close()
    print(
        f"[+] Sent DNP3 fc={function_code} frame ({len(payload)} bytes) "
        f"from {my_src_ip} to {target_ip}:{target_port}",
        file=sys.stderr,
    )
    return my_src_ip


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-ip", default="10.1.10.10", help="cc_scada_masterのIP(既定)")
    parser.add_argument("--target-port", type=int, default=20000)
    parser.add_argument("--function-code", type=int, default=1, help="1=READ")
    args = parser.parse_args()

    src_ip = send_dnp3(args.target_ip, args.target_port, args.function_code)
    # 正解ラベルの記録はこのスクリプトの責務ではない(上記docstring参照)。
    # オペレータが record_ground_truth.py を、cc_lanに接続された評価用ホスト
    # (eval_harness)から別途実行する。
    print(
        f"[i] 正解ラベルの記録は record_ground_truth.py --src-ip {src_ip} "
        f"--dst-ip {args.target_ip} --expect-violation で行ってください",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

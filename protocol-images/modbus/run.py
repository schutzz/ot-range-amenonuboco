#!/usr/bin/env python3
"""Modbus/TCP の機器役（サーバ）とポーリング役（クライアント）。

サイバーレンジの資産として置くための最小実装。環境変数で役割と接続先を
変えられるようにしてあり、同じイメージを複数の分野・複数の資産で使い回す
(使い方は docs/protocol-assets.md)。

環境変数:
    MODE      server | client        （既定: server）
    PORT      待ち受け/接続先ポート  （既定: 502）
    TARGET    接続先IP（client時のみ必須）
    INTERVAL  ポーリング間隔[秒]     （既定: 5）
    DEVICE_ID ModbusデバイスID       （既定: 1）
    REGISTERS 保持レジスタ数         （既定: 32）
    LABEL     ログに出す識別名       （既定: modbus）

サーバは保持レジスタ・入力レジスタ・コイルを持ち、クライアントは
それらを定期的に読み書きする。**両方を配置して初めて実際の通信が発生し、
構造化パイプラインが解析する対象が生まれる**（片方だけ置いても、ポートが
開いているだけで何も流れない）。
"""

from __future__ import annotations

import os
import random
import sys
import time


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


LABEL = env("LABEL", "modbus")
PORT = env_int("PORT", 502)
DEVICE_ID = env_int("DEVICE_ID", 1)


def log(message: str) -> None:
    # バッファリングされるとコンテナログに出るタイミングがずれ、実機確認時に
    # 「動いていないように見える」ため、都度フラッシュする。
    print(f"[{LABEL}] {message}", flush=True)


def run_server() -> None:
    from pymodbus.datastore import (
        ModbusSequentialDataBlock,
        ModbusServerContext,
        ModbusSlaveContext,
    )
    from pymodbus.server import StartTcpServer

    size = env_int("REGISTERS", 32)
    # プロセス値らしい初期値を入れておく（クライアントが読んだ時に
    # 0だけが並ぶより、構造化されたデータを見た時に意味が分かりやすい）。
    holding = [random.randint(100, 900) for _ in range(size)]

    device = ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, holding),
        ir=ModbusSequentialDataBlock(0, list(holding)),
        co=ModbusSequentialDataBlock(0, [False] * size),
        di=ModbusSequentialDataBlock(0, [False] * size),
    )
    context = ModbusServerContext(slaves=device, single=True)

    log(f"Modbus/TCP server listening on 0.0.0.0:{PORT} (registers={size})")
    StartTcpServer(context=context, address=("0.0.0.0", PORT))


def run_client() -> None:
    from pymodbus.client import ModbusTcpClient

    target = env("TARGET")
    if not target:
        log("TARGET が未設定です（MODE=client では接続先IPが必須）")
        sys.exit(1)

    interval = env_float("INTERVAL", 5)
    log(f"polling {target}:{PORT} every {interval}s (device_id={DEVICE_ID})")

    while True:
        client = ModbusTcpClient(target, port=PORT, timeout=5)
        try:
            if not client.connect():
                # サーバ側の起動待ちで最初の数回は失敗しうる。異常終了させず、
                # 次の周期で再試行する（起動順序に依存しない器にするため）。
                log(f"connect failed to {target}:{PORT}, retrying")
            else:
                rr = client.read_holding_registers(0, 8, slave=DEVICE_ID)
                if rr.isError():
                    log(f"read error: {rr}")
                else:
                    log(f"read holding[0:8] = {rr.registers}")

                # 読むだけでなく書き込みも行う。書き込み要求は読み取り要求とは
                # 別のファンクションコードになるため、構造化した時に
                # 「何をされたか」の区別が現れる。
                value = random.randint(100, 900)
                wr = client.write_register(0, value, slave=DEVICE_ID)
                if wr.isError():
                    log(f"write error: {wr}")
                else:
                    log(f"wrote holding[0] = {value}")
        except Exception as exc:  # noqa: BLE001 - レンジ資産は落とさず回し続ける
            log(f"unexpected error: {exc}")
        finally:
            client.close()
        time.sleep(interval)


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

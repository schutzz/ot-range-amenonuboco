#!/usr/bin/env python3
"""OPC UA のサーバ（機器・ゲートウェイ役）とクライアント（監視役）。

サイバーレンジの資産として置くための最小実装。環境変数で役割と接続先を
変えられるようにしてあり、同じイメージを複数の分野・複数の資産で使い回す
(使い方は docs/protocol-assets.md)。

環境変数:
    MODE      server | client        （既定: server）
    PORT      待ち受け/接続先ポート  （既定: 4840）
    TARGET    接続先IP（client時のみ必須）
    INTERVAL  読み取り/更新間隔[秒］（既定: 5）
    LABEL     ログに出す識別名       （既定: opcua）

サーバは温度・圧力・流量にあたる変数ノードを公開して周期的に値を更新し、
クライアントはそれらを定期的に読み書きする。**両方を配置して初めて実際の
通信が発生し、構造化パイプラインが解析する対象が生まれる**（片方だけ置いても、
ポートが開いているだけで何も流れない）。

**セキュリティ設定について**：匿名アクセスを許可し、暗号化なし
（SecurityPolicy None）で待ち受ける。OT現場でよく見られる設定であり、
かつ**暗号化するとパケットの中身が構造化できなくなる**ため、観測対象の
レンジとしては平文であることが前提になる。
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import sys

# asyncua は既定で大量のデバッグログを出す。コンテナログを実機確認に使うため、
# ライブラリ側は警告以上だけに絞り、こちらの log() の出力を埋もれさせない。
logging.basicConfig(level=logging.WARNING)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name) or default)
    except ValueError:
        return default


LABEL = env("LABEL", "opcua")
PORT = env_int("PORT", 4840)

# サーバとクライアントで同じ名前空間URIとノード名を使う。マニフェスト側で
# 意識させないため、イメージ内で固定にしてある。
NAMESPACE_URI = "urn:amenonuboco:opcua"
OBJECT_NAME = "ProcessUnit"
VARIABLES = [
    ("Temperature", 180.0, (150.0, 260.0)),
    ("Pressure", 3.2, (2.0, 6.0)),
    ("FlowRate", 42.0, (10.0, 90.0)),
]


def log(message: str) -> None:
    # バッファリングされるとコンテナログに出るタイミングがずれ、実機確認時に
    # 「動いていないように見える」ため、都度フラッシュする。
    print(f"[{LABEL}] {message}", flush=True)


async def run_server() -> None:
    from asyncua import Server, ua

    interval = env_int("INTERVAL", 5)
    server = Server()
    await server.init()
    # エンドポイントのホスト部は 0.0.0.0 にしておく。クライアントへ返す
    # EndpointDescription もこの値になるため、コンテナのIPを事前に知らなくても
    # 接続できる（クライアント側で接続先URLを差し替える処理が要らなくなる）。
    server.set_endpoint(f"opc.tcp://0.0.0.0:{PORT}/amenonuboco/server/")
    server.set_server_name(f"Amenonuboco OPC UA ({LABEL})")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])

    idx = await server.register_namespace(NAMESPACE_URI)
    obj = await server.nodes.objects.add_object(idx, OBJECT_NAME)

    nodes = []
    for name, initial, _bounds in VARIABLES:
        var = await obj.add_variable(idx, name, initial)
        await var.set_writable()
        nodes.append(var)

    log(f"OPC UA server listening on 0.0.0.0:{PORT} (ns={idx} {OBJECT_NAME})")
    async with server:
        while True:
            await asyncio.sleep(interval)
            for var, (name, _initial, (low, high)) in zip(nodes, VARIABLES):
                await var.write_value(round(random.uniform(low, high), 2))


async def run_client() -> None:
    from asyncua import Client

    target = env("TARGET")
    if not target:
        log("TARGET が未設定です（MODE=client では接続先IPが必須）")
        sys.exit(1)

    interval = env_int("INTERVAL", 5)
    url = f"opc.tcp://{target}:{PORT}/amenonuboco/server/"
    log(f"polling {url} every {interval}s")

    while True:
        try:
            async with Client(url=url, timeout=10) as client:
                idx = await client.get_namespace_index(NAMESPACE_URI)
                nodes = [
                    await client.nodes.root.get_child(
                        ["0:Objects", f"{idx}:{OBJECT_NAME}", f"{idx}:{name}"]
                    )
                    for name, _initial, _bounds in VARIABLES
                ]
                while True:
                    values = [await node.read_value() for node in nodes]
                    log(
                        "read "
                        + ", ".join(
                            f"{name}={value}"
                            for (name, _i, _b), value in zip(VARIABLES, values)
                        )
                    )

                    # 読むだけでなく書き込みも行う。書き込みは Read とは別の
                    # サービス（Write）になるため、構造化した時に
                    # 「何をされたか」の区別が現れる。
                    name, _initial, (low, high) = VARIABLES[0]
                    new_value = round(random.uniform(low, high), 2)
                    await nodes[0].write_value(new_value)
                    log(f"wrote {name} = {new_value}")

                    await asyncio.sleep(interval)
        except Exception as exc:  # noqa: BLE001 - レンジ資産は落とさず回し続ける
            # サーバ側の起動待ちで最初の数回は失敗しうる。異常終了させず、
            # 次の周期で再接続する（起動順序に依存しない器にするため）。
            log(f"connection error: {exc}, retrying in {interval}s")
            await asyncio.sleep(interval)


def main() -> None:
    mode = env("MODE", "server").lower()
    if mode == "server":
        asyncio.run(run_server())
    elif mode == "client":
        asyncio.run(run_client())
    else:
        log(f"未知の MODE '{mode}'（server または client を指定してください）")
        sys.exit(1)


if __name__ == "__main__":
    main()

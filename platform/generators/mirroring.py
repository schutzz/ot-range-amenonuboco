"""マニフェストのinstrumentation層から、tcベースのミラーリング設定シェル
コマンド列を生成する(Phase2)。

ミラーリング設定の実行主体は、常に`topology.routing.gateway`で指定された資産
(role: l3-router)である。ゲートウェイは全観測対象セグメントに接続している
前提のため、tcミラーリングを設定できる唯一の資産になる(前身ot-ids-verumの
`wan_router`/`setup_mirror.sh`と同じ構造)。

設計方針(詳細はPhase2-Instrumentation.md 2節):
- 決定事項#29: インターフェース名は常にIPアドレスからの動的逆引きで解決する。
  固定インターフェース名(eth0等)を生成物に埋め込まない。
- 決定事項#30: `tc qdisc`/`tc filter`は必ずペアで冪等化する
  (`tc filter del`を`add`の直前に置く4行1セットのテンプレート)。
"""

from __future__ import annotations

from schema import Asset, Instrumentation, Topology

from .shell import resolve_interface_snippet


class MirroringGenerationError(Exception):
    """ミラーリング設定生成時のエラー(ゲートウェイのIP未設定等)。"""


def _require_gateway(topology: Topology) -> Asset:
    if topology.routing is None:
        raise MirroringGenerationError(
            "instrumentation層を使うには topology.routing が必須です"
            "(ゲートウェイ資産が全セグメントに接続する唯一のミラーリング実行点になるため)"
        )
    return topology.asset_by_name(topology.routing.gateway)


def _require_gateway_ip(gateway: Asset, segment_name: str) -> str:
    ip = gateway.ip_on_segment(segment_name)
    if ip is None:
        raise MirroringGenerationError(
            f"gateway asset '{gateway.name}' has no static ip on segment "
            f"'{segment_name}'; mirroring generation requires a fixed gateway ip "
            f"on every observed segment and on mirror_to"
        )
    return ip


def _idempotent_mirror_block(segment_if_var: str, mirror_if_var: str) -> list[str]:
    """1セグメント分の冪等化済みtcミラーリング設定(決定事項#30)。
    `tc filter del`を`add`の直前に必ず置く4行1セットで、片方だけ冪等化する
    経路を作らない。
    """
    return [
        f"tc qdisc add dev ${segment_if_var} handle ffff: ingress 2>/dev/null",
        f"tc filter del dev ${segment_if_var} parent ffff: 2>/dev/null",
        f"tc filter add dev ${segment_if_var} parent ffff: protocol all u32 "
        f"match u32 0 0 action mirred egress mirror dev ${mirror_if_var}",
    ]


def _mirror_egress_broadcast_block(mirror_if_var: str) -> list[str]:
    """ミラー先IFのegressで、送出フレームの宛先MACをブロードキャストに書き換える
    冪等化済みブロック(決定事項#116、罠ログ#031)。

    背景: tcミラーリング(ingress mirred)は両方向のパケットを正しくミラー先IFへ
    送出するが、ミラーコピーの宛先MACは「元パケットが宛てていたゲートウェイ自身の
    受信IF MAC」という、観測用セグメント(mirror_link)のDockerブリッジから見れば
    "よそ者MAC"になる。Linuxブリッジはこの unknown-unicast を確実にはフラッディング
    せず(MAC学習状態・タイミング依存)、観測ノード(structurer/observer)へ届く方向が
    片方向に偏る・実行のたびに変わる、という非決定的な取りこぼしが起きる。
    SNMP/ENIP等の単発・片方向の攻撃検知では表面化しなかったが、VNC等の
    ステートフルな双方向TCPセッションでは、クライアント側メッセージ(キー入力等)を
    含む片方向が丸ごと欠落し、tsharkが状態を再構成できずキーストローク内容を
    構造化できなくなる(実機切り分けで特定)。

    対策: ミラー先IFのegress(=ミラーコピーだけがほぼ独占的に流れる経路)で宛先MACを
    ブロードキャスト(ff:ff:ff:ff:ff:ff)へ書き換える。ブロードキャストフレームは
    ブリッジが常に全ポートへ配送するため、観測ノードは両方向を確実に受信できる。
    観測ノードはIP層で自分宛でないフレームを破棄するだけで実害はない。
    """
    return [
        f"tc qdisc add dev ${mirror_if_var} root handle 1: prio 2>/dev/null",
        f"tc filter del dev ${mirror_if_var} parent 1: 2>/dev/null",
        f"tc filter add dev ${mirror_if_var} parent 1: protocol all u32 "
        f"match u32 0 0 action pedit ex munge eth dst set ff:ff:ff:ff:ff:ff",
    ]


def generate_mirroring_commands(
    topology: Topology, instrumentation: Instrumentation
) -> list[str]:
    """ゲートウェイ資産の起動コマンドに注入する、ミラーリング設定シェル
    コマンド列を返す。呼び出し元(generators/compose.py)は、これを
    パッケージ導入の直後・ルーティング設定より前に配置する(決定事項#31)。
    """
    gateway = _require_gateway(topology)

    mirror_ip = _require_gateway_ip(gateway, instrumentation.mirror_to)
    commands: list[str] = [resolve_interface_snippet("MIRROR_IF", mirror_ip)]
    # ミラー先IFのegress宛先MACブロードキャスト書換(決定事項#116)。個々の
    # セグメントのingressミラー設定より先に置く(ミラーコピーが流れ始める前に
    # 書換規則を用意しておく)。
    commands.extend(_mirror_egress_broadcast_block("MIRROR_IF"))

    for segment in instrumentation.observed_segments(topology):
        seg_ip = _require_gateway_ip(gateway, segment.name)
        var_name = f"{segment.name.upper()}_IF"
        commands.append(resolve_interface_snippet(var_name, seg_ip))
        commands.extend(_idempotent_mirror_block(var_name, "MIRROR_IF"))

    return commands

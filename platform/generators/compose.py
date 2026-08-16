"""topology層のマニフェストから docker-compose.yml を生成する(Phase1決定事項#14)。

生成方針:
- セグメント → 固定サブネットのbridgeネットワーク
- 資産 → サービス。image/build・cap_add/sysctls/ports(プリセット+overrides合成)・
  networks(マルチホーム対応)を展開
- ルーティング → routing.gateway を経由し、資産が直接接続していない全セグメントへの
  経路を起動コマンドのシェルラッパーとして生成する(Phase1決定事項#16)。マニフェスト
  自体には ip route add は一切現れない(Phase0決定事項#9)。
"""

from __future__ import annotations

from typing import Any

import yaml

from schema import (
    Asset,
    Instrumentation,
    Manifest,
    RolePresets,
    Segment,
    Topology,
    resolve_effective_attributes,
)

from .mirroring import MirroringGenerationError, generate_mirroring_commands


class ComposeGenerationError(Exception):
    """docker-compose.yml 生成時のエラー(ルーティング解決不能等)。"""


def _network_block(segments: list[Segment]) -> dict[str, Any]:
    networks: dict[str, Any] = {}
    for seg in segments:
        networks[seg.name] = {
            "driver": "bridge",
            "ipam": {"config": [{"subnet": seg.cidr}]},
            "labels": {"amenonuboco.segment.kind": seg.kind},
        }
    return networks


def _gateway_ip_on_segment(gateway: Asset, segment_name: str) -> str:
    ip = gateway.ip_on_segment(segment_name)
    if ip is None:
        raise ComposeGenerationError(
            f"gateway asset '{gateway.name}' has no static ip on segment "
            f"'{segment_name}' (either not connected, or ip left for dynamic "
            f"assignment); routing generation requires a fixed gateway ip"
        )
    return ip


def _routing_commands(topology: Topology, asset: Asset) -> list[str]:
    """assetが直接接続していない全セグメントへの`ip route add`コマンド一覧を返す。
    routing未指定、またはasset自身がgatewayの場合は空リスト。

    複数セグメントに接続する資産は、最初の接続セグメント(asset.networks[0])を
    「上流」とみなし、そのセグメント上でのgateway IPを経由先として使う
    (Phase1決定事項#20: 経由先の選び方の簡略化)。
    """
    if topology.routing is None:
        return []
    if asset.name == topology.routing.gateway:
        return []
    if not asset.networks:
        return []

    gateway = topology.asset_by_name(topology.routing.gateway)
    uplink_segment = asset.networks[0].segment
    via_ip = _gateway_ip_on_segment(gateway, uplink_segment)

    unreached = topology.segments_reachable_via_gateway(asset)
    return [f"ip route add {seg.cidr} via {via_ip}" for seg in unreached]


# iproute2導入をapt-get(Debian系)/apk(Alpine系)いずれでも動くよう自動判定する。
# verum実データにはDebian系(debian:bullseye-slim, python:3.10-slim)とAlpine系
# (nodered/node-red, timberio/vector:...-alpine)が混在しており、どちらかに
# 決め打ちすると他方のイメージで確実に壊れる(Phase1決定事項#21)。
_INSTALL_IPROUTE2 = (
    "(command -v apt-get >/dev/null 2>&1 && apt-get update -qq && "
    "apt-get install -y -qq iproute2 >/dev/null 2>&1) || "
    "(command -v apk >/dev/null 2>&1 && apk add --no-cache -q iproute2 >/dev/null 2>&1)"
)


def _assemble_command(
    mirroring_cmds: list[str], routing_cmds: list[str], app_command: str | None
) -> str | None:
    """ミラーリング設定 + ルーティング + アプリ起動 を1本のshellコマンドに合成する。

    実行順序はミラーリング→ルーティング→アプリ起動に固定する(Phase2決定事項#31、
    観測基盤を経路設定より先に整えておく)。

    **overrides.command が明示されている資産にのみ適用する**(呼び出し元
    _service_block が routing_cmds/mirroring_cmds の算出自体をこの条件で制御
    する)。app_command が無ければNoneを返し、イメージ既定のENTRYPOINT/CMDを
    一切上書きしない(elasticsearch/vector等、ベースイメージ自身の起動スクリプト
    に依存するコンテナを壊さないため。Phase1決定事項#22)。

    シェルは`sh`を使う(bashが無いAlpine系イメージでも動くように)。
    """
    if not app_command:
        return None

    parts: list[str] = []
    if mirroring_cmds or routing_cmds:
        parts.append(_INSTALL_IPROUTE2)
        parts.extend(mirroring_cmds)
        parts.extend(routing_cmds)
    parts.append(app_command)

    joined = " && ".join(parts)
    # Docker Compose自体が command 文字列中の $VAR / $(...) を「Composeの変数
    # 展開対象」として解釈してしまい、シェルに渡る前に空文字列へ置換して
    # しまう(前身ot-ids-verumの罠ログ#052と同型: 補間機構がテキストレベルで
    # 素通しに働き、意図しない箇所にまで及ぶ)。Composeの仕様上、リテラルの
    # `$`は`$$`とエスケープする必要があるため、シェル変数参照・コマンド置換を
    # 含む生成コマンド全体に対して機械的に適用する(Phase2決定事項#34)。
    escaped = joined.replace("$", "$$")
    return f'sh -c "{escaped}"'


_OBSERVATION_KIND = "observation"


def _needs_mirror_ip_forward_guard(topology: Topology, asset: Asset) -> bool:
    """観測用セグメント(kind=observation、例: mirror_link)と他セグメントに同時接続
    する資産は、意図しないip_forward有効化のリスクを持つ(前身ot-ids-verumが実際に
    踏んだ罠、決定事項#45〜#47相当)。l3-routerロールは意図的にip_forwardを有効化
    する役割のため対象外とする(Phase1決定事項#19)。
    """
    if asset.role == "l3-router":
        return False
    seg_names = {net.segment for net in asset.networks}
    if len(seg_names) < 2:
        return False
    kinds = {
        topology.segment_by_name(s).kind
        for s in seg_names
        if s in {seg.name for seg in topology.segments}
    }
    return _OBSERVATION_KIND in kinds


def _mirroring_commands_for_asset(
    asset: Asset,
    topology: Topology,
    instrumentation: Instrumentation | None,
    resolved_cap_add: list[str],
) -> list[str]:
    """ミラーリング設定は、①instrumentation層が宣言されており、②この資産が
    ゲートウェイ(mirroring実行点、generators/mirroring.py参照)であり、
    ③実際にNET_ADMINを保持している場合にのみ算出する。②③はルーティング
    (決定事項#22・#25)と同じ考え方——ゲートウェイ以外にミラーリング設定を
    仕込む意味は無く、NET_ADMINが無ければ`tc`コマンド自体が失敗して罠#005と
    同型のクラッシュを招く(Phase2決定事項#33)。
    """
    if instrumentation is None:
        return []
    if topology.routing is None or asset.name != topology.routing.gateway:
        return []
    if "NET_ADMIN" not in resolved_cap_add:
        return []
    return generate_mirroring_commands(topology, instrumentation)


def _service_block(
    asset: Asset,
    topology: Topology,
    presets: RolePresets,
    instrumentation: Instrumentation | None,
) -> dict[str, Any]:
    resolved = resolve_effective_attributes(asset, presets)

    # container_name をあえて設定しない(Phase1決定事項#24)。前身(ot-ids-verum)は
    # 資産名をそのままcontainer_nameに使っていたが、これだとホスト上で同名の
    # コンテナが既に動いていると衝突する。Amenonuboco自身の目的(複数のサイバー
    # レンジを動的に立ち上げる)には根本的に不向きなため、Compose標準の
    # プロジェクトスコープ命名(<project>_<service>_<n>)に委ねる。
    service: dict[str, Any] = {}
    if asset.image.startswith("./") or asset.image.startswith("../"):
        service["build"] = asset.image
    else:
        service["image"] = asset.image

    if resolved.cap_add:
        service["cap_add"] = resolved.cap_add

    sysctls = list(resolved.sysctls)
    if _needs_mirror_ip_forward_guard(topology, asset) and not any(
        s.startswith("net.ipv4.ip_forward") for s in sysctls
    ):
        sysctls.append("net.ipv4.ip_forward=0")
    if sysctls:
        service["sysctls"] = sysctls

    if resolved.ports:
        service["ports"] = resolved.ports

    net_block: dict[str, Any] = {}
    for net in asset.networks:
        net_block[net.segment] = {"ipv4_address": net.ip} if net.ip else {}
    service["networks"] = net_block

    # ルーティングは、①overrides.commandが明示されており(決定事項#22)、
    # かつ②実際にNET_ADMINを保持している資産にのみ算出する。NET_ADMINが
    # 無いと`ip route add`自体が"Operation not permitted"で失敗し、&&で
    # 繋いだ後続のアプリ起動コマンドごと道連れにしてしまう(罠ログ#005)。
    needs_routing = bool(resolved.command) and "NET_ADMIN" in resolved.cap_add
    routing_cmds = _routing_commands(topology, asset) if needs_routing else []
    mirroring_cmds = (
        _mirroring_commands_for_asset(asset, topology, instrumentation, resolved.cap_add)
        if resolved.command
        else []
    )
    command = _assemble_command(mirroring_cmds, routing_cmds, resolved.command)
    if command:
        service["command"] = command

    service["restart"] = "unless-stopped"
    return service


def generate_compose(manifest: Manifest, presets: RolePresets) -> dict[str, Any]:
    """マニフェストのtopology層(+instrumentation層があれば計装も)から
    docker-compose.yml 相当の辞書を生成する。
    """
    topology = manifest.topology
    try:
        return {
            "networks": _network_block(topology.segments),
            "services": {
                asset.name: _service_block(
                    asset, topology, presets, manifest.instrumentation
                )
                for asset in topology.assets
            },
        }
    except MirroringGenerationError as exc:
        raise ComposeGenerationError(str(exc)) from exc


def dump_compose_yaml(compose: dict[str, Any]) -> str:
    header = (
        "# amenonuboco: このファイルは manifests/*.yaml から自動生成されました。\n"
        "# 直接編集せず、マニフェスト側を編集して再生成してください。\n"
    )
    body = yaml.safe_dump(compose, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return header + body

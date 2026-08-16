"""マニフェストのトポロジ層(topology)を表す Pydantic モデル。

Phase 1のスコープは topology 層のみ。instrumentation/structuring/detection/attack は
Phase 2以降でモデル化するまで、未検証の生データ(dict)として保持するだけに留める
(Phase0-ManifestSchema.md / Phase1-Provisioner.md 参照。フィールド定義は
docs/manifest-schema-guide.md の記法と一致させている)。
"""

from __future__ import annotations

import ipaddress
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

# --- 語彙(docs/manifest-schema-guide.md §5、Phase0決定事項#8) -----------------

SegmentKind = Literal[
    "it-core",
    "wan-edge",
    "ot-l2",
    "ot-lan",
    "observation",
    "dmz",
]

AssetRole = Literal[
    "ot-asset",
    "l3-router",
    "detection-infra",
    "observer",
    "structurer",  # Phase3決定事項#41: 構造化パイプライン(tshark+バルクローダー)実行ノード
    "eval-harness",
    "attacker-external",
    "attacker-internal",
    "attacker-insider",
]


class Metadata(BaseModel):
    name: str
    description: Optional[str] = None


class Segment(BaseModel):
    name: str
    cidr: str
    kind: SegmentKind

    @model_validator(mode="after")
    def _validate_cidr(self) -> "Segment":
        try:
            ipaddress.ip_network(self.cidr, strict=True)
        except ValueError as exc:
            raise ValueError(
                f"segment '{self.name}': invalid cidr '{self.cidr}': {exc}"
            ) from exc
        return self


class AssetNetwork(BaseModel):
    """資産が接続するセグメント1本分。マルチホームのため Asset.networks は必ず配列
    (Phase0決定事項#7)。ip 省略時はプロビジョナ側の動的割当に委ねる。
    """

    segment: str
    ip: Optional[str] = None

    @model_validator(mode="after")
    def _validate_ip(self) -> "AssetNetwork":
        if self.ip is not None:
            try:
                ipaddress.ip_address(self.ip)
            except ValueError as exc:
                raise ValueError(f"invalid ip '{self.ip}': {exc}") from exc
        return self


class AssetOverrides(BaseModel):
    """ロールプリセット(Phase1決定事項#15)への差分上書き(Phase0決定事項#10)。"""

    ports: list[str] = Field(default_factory=list)
    command: Optional[str] = None
    cap_add: Optional[list[str]] = None
    sysctls: Optional[list[str]] = None
    # コンテナの環境変数(`KEY=VALUE`形式、Docker Composeの`environment`と同じ記法)。
    # ports/commandと同じくロールプリセット側に概念が無いため、常にoverridesの値
    # をそのまま使う(加算/上書きの曖昧さが生じない)。Phase3実機検証で、
    # elasticsearchが既定でTLS必須(xpack.security.enabled)で起動し、
    # es_enrich_refresher/structurerいずれのプレーンHTTPも到達できないことが
    # 判明して追加した(Phase3決定事項#48、罠ログ#011)。
    environment: list[str] = Field(default_factory=list)


class Asset(BaseModel):
    name: str
    role: AssetRole
    image: str
    networks: list[AssetNetwork] = Field(min_length=1)
    overrides: AssetOverrides = Field(default_factory=AssetOverrides)

    def ip_on_segment(self, segment_name: str) -> Optional[str]:
        """指定セグメント上でのこの資産の静的IPを返す(無ければNone、動的割当や
        非接続の場合)。generators/compose.py・generators/mirroring.py の両方が
        参照する共通ヘルパー(決定事項#29の動的解決の起点になる、gatewayの
        既知IPを求める処理で使う)。
        """
        for net in self.networks:
            if net.segment == segment_name:
                return net.ip
        return None


class Routing(BaseModel):
    """gateway で指定した資産(role=l3-router)を経由し、各資産が自セグメント以外の
    全セグメントへの経路を持つよう、プロビジョナ側で自動生成する(Phase1決定事項#16)。
    """

    gateway: str


class Topology(BaseModel):
    segments: list[Segment]
    assets: list[Asset]
    routing: Optional[Routing] = None

    @model_validator(mode="after")
    def _validate_cross_references(self) -> "Topology":
        # 重複名チェック
        seg_names: list[str] = [s.name for s in self.segments]
        if len(seg_names) != len(set(seg_names)):
            dupes = {n for n in seg_names if seg_names.count(n) > 1}
            raise ValueError(f"duplicate segment name(s): {sorted(dupes)}")

        asset_names: list[str] = [a.name for a in self.assets]
        if len(asset_names) != len(set(asset_names)):
            dupes = {n for n in asset_names if asset_names.count(n) > 1}
            raise ValueError(f"duplicate asset name(s): {sorted(dupes)}")

        segment_name_set = set(seg_names)
        asset_name_set = set(asset_names)

        # 資産が参照するセグメントが実在するか
        for asset in self.assets:
            for net in asset.networks:
                if net.segment not in segment_name_set:
                    raise ValueError(
                        f"asset '{asset.name}' references undefined segment "
                        f"'{net.segment}'"
                    )

        # routing.gateway が実在する l3-router 資産を指しているか
        if self.routing is not None:
            gw_name = self.routing.gateway
            if gw_name not in asset_name_set:
                raise ValueError(
                    f"routing.gateway '{gw_name}' does not reference a defined asset"
                )
            gateway_asset = next(a for a in self.assets if a.name == gw_name)
            if gateway_asset.role != "l3-router":
                raise ValueError(
                    f"routing.gateway '{gw_name}' must have role 'l3-router' "
                    f"(has '{gateway_asset.role}')"
                )

        return self

    def segments_reachable_via_gateway(self, asset: Asset) -> list[Segment]:
        """資産が直接接続していないセグメント一覧(gateway経由で到達すべき経路の対象)。
        gateway資産自身には呼ばない想定(generators/compose.py 側でスキップする)。
        """
        connected = {net.segment for net in asset.networks}
        return [s for s in self.segments if s.name not in connected]

    def segment_by_name(self, name: str) -> Segment:
        for s in self.segments:
            if s.name == name:
                return s
        raise KeyError(f"no such segment: {name}")

    def asset_by_name(self, name: str) -> Asset:
        for a in self.assets:
            if a.name == name:
                return a
        raise KeyError(f"no such asset: {name}")


class Manifest(BaseModel):
    """マニフェスト全体。detection/attack はまだモデル化するまで、未検証の
    生データ(dict)として保持するのみ。instrumentation(Phase2)・structuring
    (Phase3)はモデル化済み。
    """

    model_config = {"populate_by_name": True}

    api_version: str = Field(alias="apiVersion")
    kind: Literal["CyberRange"]
    metadata: Metadata
    topology: Topology
    instrumentation: Optional["Instrumentation"] = None
    structuring: Optional["Structuring"] = None

    # Phase 4以降でモデル化するまでの暫定(未検証の生データ)
    detection: Optional[dict] = None
    attack: Optional[dict] = None

    @model_validator(mode="after")
    def _validate_instrumentation_references(self) -> "Manifest":
        if self.instrumentation is not None:
            from .instrumentation import validate_instrumentation

            validate_instrumentation(self.instrumentation, self.topology)
        return self


# 循環import回避のための遅延解決(instrumentation.py が topology.py の Segment/Topology
# を参照するため、Manifestの型ヒントは文字列参照にしておき、ここで解決する)。
# structuring.py はtopology.pyに依存しないため循環の心配はないが、統一的に
# ここでまとめて解決する。
from .instrumentation import Instrumentation  # noqa: E402
from .structuring import Structuring  # noqa: E402

Manifest.model_rebuild()

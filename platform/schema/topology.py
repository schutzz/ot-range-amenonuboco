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


class Asset(BaseModel):
    name: str
    role: AssetRole
    image: str
    networks: list[AssetNetwork] = Field(min_length=1)
    overrides: AssetOverrides = Field(default_factory=AssetOverrides)


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
    """マニフェスト全体。Phase 1では topology 以外の層は生データのまま保持するのみ
    (バリデーションもモデル化もしない)。
    """

    model_config = {"populate_by_name": True}

    api_version: str = Field(alias="apiVersion")
    kind: Literal["CyberRange"]
    metadata: Metadata
    topology: Topology

    # Phase 2以降でモデル化するまでの暫定(未検証の生データ)
    instrumentation: Optional[dict] = None
    structuring: Optional[dict] = None
    detection: Optional[dict] = None
    attack: Optional[dict] = None

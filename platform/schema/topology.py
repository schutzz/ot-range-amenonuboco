"""マニフェストのトポロジ層(topology)を表す Pydantic モデル。

Phase 1のスコープは topology 層のみ。instrumentation/structuring/detection/attack は
Phase 2以降でモデル化するまで、未検証の生データ(dict)として保持するだけに留める
(Phase0-ManifestSchema.md / Phase1-Provisioner.md 参照。フィールド定義は
docs/manifest-schema-guide.md の記法と一致させている)。
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
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
    "security-lan",  # Phase7決定事項#104: 物理セキュリティ網(監視カメラ・入退室管理等)
]

AssetRole = Literal[
    "ot-asset",
    "l3-router",
    "detection-infra",
    "observer",
    "structurer",  # Phase3決定事項#41: 構造化パイプライン(tshark+バルクローダー)実行ノード
    "eval-harness",
    "attack-engine",  # Phase4決定事項#58: 攻撃エミュレーションエンジン(Caldera server)
    "visualization-engine",  # Phase6決定事項#83: 可視化エンジン(Grafana等)
    "attacker-external",
    "attacker-internal",
    "attacker-insider",
    "security-asset",  # Phase7決定事項#104: 物理セキュリティ資産(NVR/カメラ/入退室管理パネル)
    "remote-access-gateway",  # Phase7決定事項#105: 正規リモート保守経路(侵害の起点になりうる、Oldsmar型)
]


class Metadata(BaseModel):
    name: str
    description: Optional[str] = None


class ImpairmentSpec(BaseModel):
    """tc-netem によるセグメント上位リンク（バックホール）の下り方向の回線劣化仕様。

    Phase 10 決定事項#144/#153: `impairment` は「このセグメントへの下り方向のみ」
    ——ゲートウェイの該当セグメント向きIF の egress root qdisc に netem をアタッチする。
    * 上り方向（セグメント→ゲートウェイ）は無制限のまま（非対称）。
    * 同一セグメント内の通信（ゲートウェイを経由しない）には一切効かない。
    mirror_to 指定セグメントへの宣言は Manifest レベルのバリデーションで拒否する（決定事項#154）。
    """

    delay: Optional[str] = None    # 例: "100ms"
    jitter: Optional[str] = None   # 例: "20ms"
    loss: Optional[str] = None     # 例: "1.5%"
    rate: Optional[str] = None     # 例: "9600bit"（レガシーシリアル変換器等の低速帯域）


class Segment(BaseModel):
    name: str
    cidr: str
    kind: SegmentKind
    # Phase 10 決定事項#144: OT 回線劣化エミュレーション（オプション）
    impairment: Optional[ImpairmentSpec] = None

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


class PhysicalProcessSpec(BaseModel):
    """物理プロセス（Digital Twin）の離散時間モデル仕様。

    Phase 10 決定事項#146/#152: PLC/RTU 資産に物理プロセスモデルを宣言可能にする。
    `observed_by` は必須フィールド——省略すると物理エンジンがレジスタを更新しても
    ワイヤにパケットが出ず、tshark は何も観測できない（宣言したのに可視化されない
    という historian 型の失敗：決定事項#151 と同型）。
    さらに `observed_by` が指す資産がこの PLC と同一セグメントにある場合も
    同様の問題（同一セグメント内通信はゲートウェイを経由しないためミラーされない）
    を引き起こすため、Manifest レベルのバリデーションで別セグメント配置を強制する
    （決定事項#152）。
    """

    type: str               # 物理モデルの種別: "tank_level", "temperature" 等
    initial_level: float = 0.0
    capacity: float = 100.0
    update_interval: str = "1.0s"  # 計算・レジスタ更新の周期
    bind_registers: dict[str, int] = Field(default_factory=dict)
    # 必須: 物理値をポーリングする資産名（別セグメント必須）
    observed_by: str


class Asset(BaseModel):
    name: str
    role: AssetRole
    image: str
    networks: list[AssetNetwork] = Field(min_length=1)
    overrides: AssetOverrides = Field(default_factory=AssetOverrides)
    # Phase 10 決定事項#146: 物理プロセス（Digital Twin）モデル（オプション）
    physical_process: Optional[PhysicalProcessSpec] = None

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
        segments_by_name = {s.name: s for s in self.segments}

        # 資産が参照するセグメントが実在するか。あわせて、同一資産が同じ
        # セグメントに二重接続していないか、宣言したIPがそのセグメントの
        # CIDR範囲に収まっているかも検証する(Phase5後の地盤固めで追加、
        # 決定事項#75)。いずれも「宣言としては通るが docker compose up で
        # 初めて壊れる/意図せず動く」類の穴であり、宣言時に弾く。
        for asset in self.assets:
            connected_segments: set[str] = set()
            for net in asset.networks:
                if net.segment not in segment_name_set:
                    raise ValueError(
                        f"asset '{asset.name}' references undefined segment "
                        f"'{net.segment}'"
                    )
                if net.segment in connected_segments:
                    raise ValueError(
                        f"asset '{asset.name}' connects to segment "
                        f"'{net.segment}' more than once"
                    )
                connected_segments.add(net.segment)
                if net.ip is not None:
                    seg = segments_by_name[net.segment]
                    if ipaddress.ip_address(net.ip) not in ipaddress.ip_network(
                        seg.cidr, strict=True
                    ):
                        raise ValueError(
                            f"asset '{asset.name}' ip '{net.ip}' is not within "
                            f"the cidr '{seg.cidr}' of segment '{net.segment}'"
                        )

        # 同一セグメント内でのIP重複チェック(決定事項#75)。前身ot-ids-verumの
        # サブネット/IP衝突(罠#004)と同種で、docker compose up時にDockerが
        # 弾く前に宣言レベルで検出する。
        ips_per_segment: dict[str, dict[str, str]] = {}
        for asset in self.assets:
            for net in asset.networks:
                if net.ip is None:
                    continue
                seen = ips_per_segment.setdefault(net.segment, {})
                if net.ip in seen:
                    raise ValueError(
                        f"duplicate ip '{net.ip}' on segment '{net.segment}': "
                        f"used by both '{seen[net.ip]}' and '{asset.name}'"
                    )
                seen[net.ip] = asset.name

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
    """マニフェスト全体。5層すべてをモデル化済み(instrumentation=Phase2、
    structuring=Phase3、detection/attack=Phase4)。トポロジ層以外はすべて任意で
    あり、宣言が無ければ対応する生成を一切行わない。
    """

    model_config = {"populate_by_name": True}

    api_version: str = Field(alias="apiVersion")
    kind: Literal["CyberRange"]
    metadata: Metadata
    topology: Topology
    instrumentation: Optional["Instrumentation"] = None
    structuring: Optional["Structuring"] = None
    detection: Optional["Detection"] = None
    attack: Optional["Attack"] = None
    visualization: Optional["Visualization"] = None

    # マニフェスト自身が置かれているディレクトリ(loaderが読み込み時に設定する)。
    # 相対パスで書かれた外部資産参照(detection.plugins[].source、Calderaの
    # abilities_path等)を解決する基点になる。マニフェストの宣言内容ではなく
    # 「どこから読んだか」というメタ情報のため、シリアライズ対象から除外する。
    # 未設定(dictから直接model_validateした場合)はカレントディレクトリ基点に
    # フォールバックする(Phase4決定事項#60)。
    source_dir: Optional[Path] = Field(default=None, exclude=True)

    def resolve_path(self, path_str: str) -> Path:
        """マニフェスト内に書かれた外部資産パスを絶対パスへ解決する。"""
        p = Path(path_str)
        if p.is_absolute():
            return p
        base = self.source_dir if self.source_dir is not None else Path.cwd()
        return (base / p).resolve()

    @model_validator(mode="after")
    def _validate_cross_layer_references(self) -> "Manifest":
        """層をまたぐ相互参照の検証。各層のモデル単体はtopologyを知らないため、
        クロスバリデーションはここでまとめて行う(Phase2で確立した方式)。
        """
        if self.instrumentation is not None:
            from .instrumentation import validate_instrumentation

            validate_instrumentation(self.instrumentation, self.topology)

        if self.detection is not None:
            from .detection import validate_detection

            validate_detection(self.detection, self.topology)

        if self.attack is not None:
            from .attack import validate_attack

            validate_attack(self.attack, self.topology)

        if self.visualization is not None:
            from .visualization import validate_visualization

            validate_visualization(self.visualization, self.topology)

        # structuring層はミラーされたトラフィックを構造化する層であり、
        # instrumentation層(ミラーリング)が前提になる。structuringだけを宣言
        # してinstrumentationを宣言しないと、structurer資産の起動コマンドが
        # 生成されず(compose.py側でミラー元が無いため)、tsharkパイプラインが
        # 「宣言したのに静かに動かない」状態になる。これはPhase4でattack.nodes
        # を廃した理由(生成器が静かに取りこぼす、決定事項#53)と同型の問題の
        # ため、宣言時に弾く(決定事項#76)。
        if self.structuring is not None and self.structuring.protocols:
            if self.instrumentation is None:
                raise ValueError(
                    "structuring層(protocols)を宣言するには instrumentation層が"
                    "必須です(構造化はミラーされたトラフィックを対象にするため)。"
                    "instrumentation.mirror_to を宣言してください"
                )

            # 構造化パイプラインの実行主体は structurer ロールの資産(決定事項#41)。
            # generators/compose.py は structurer ロール以外の資産に対して黙って
            # 空のコマンド列を返すため、structurer が1つも無いマニフェストは
            # 「protocolsを宣言したのにtsharkが1つも起動しない」状態になる。
            # これは決定事項#76(structuring単独宣言の禁止)と同型の
            # 「宣言したのに静かに動かない」であり、同じく宣言時に弾く
            # (Phase9決定事項#127の前提整備)。
            if not any(a.role == "structurer" for a in self.topology.assets):
                raise ValueError(
                    "structuring層(protocols)を宣言するには role: structurer の"
                    "資産が最低1つ必要です(構造化パイプラインの実行主体が無いと、"
                    "宣言しても tshark が1つも起動しません)"
                )

        # Phase 10 決定事項#154: mirror_to セグメントへの impairment 宣言を禁止する。
        # mirror_link 側のゲートウェイ向け IF には決定事項#116 の宛先 MAC 書換ルール
        # (root handle 1: prio) が既に設定済みであり、netem (同じく root) をアタッチ
        # すると衝突する。観測用セグメント自体を劣化させる意味も無い。
        if self.instrumentation is not None:
            mirror_seg = self.instrumentation.mirror_to
            for seg in self.topology.segments:
                if seg.name == mirror_seg and seg.impairment is not None:
                    raise ValueError(
                        f"segment '{mirror_seg}' は instrumentation.mirror_to "
                        f"（観測用セグメント）であるため impairment を宣言できません。"
                        f"mirror_link 側には決定事項#116 の宛先 MAC 書換ルール "
                        f"(root handle 1: prio) が既に存在し、netem と衝突します "
                        f"（Phase 10 決定事項#154）"
                    )

        # Phase 10 決定事項#152: physical_process.observed_by のクロス検証。
        # ①observed_by が実在する資産を指しているか
        # ②observed_by 先の資産が物理プロセス資産と同一セグメントを共有していないか
        # （同一セグメント内通信はゲートウェイを経由せずミラーされないため）
        asset_map = {a.name: a for a in self.topology.assets}
        for asset in self.topology.assets:
            if asset.physical_process is None:
                continue
            observer_name = asset.physical_process.observed_by
            if observer_name not in asset_map:
                raise ValueError(
                    f"asset '{asset.name}' の physical_process.observed_by "
                    f"'{observer_name}' は存在しない資産を指しています"
                )
            observer = asset_map[observer_name]
            plc_segments = {net.segment for net in asset.networks}
            observer_segments = {net.segment for net in observer.networks}
            shared = plc_segments & observer_segments
            if shared:
                raise ValueError(
                    f"asset '{asset.name}' の physical_process.observed_by が指す "
                    f"'{observer_name}' は、同じセグメント {sorted(shared)} 上にあります。"
                    f"同一セグメント内の通信はゲートウェイを経由しないためミラーされず、"
                    f"物理プロセスの値は構造化パイプラインに到達しません。"
                    f"別セグメントの資産を指定してください（Phase 10 決定事項#152）"
                )

        return self


# 循環import回避のための遅延解決(instrumentation.py が topology.py の Segment/Topology
# を参照するため、Manifestの型ヒントは文字列参照にしておき、ここで解決する)。
# structuring.py はtopology.pyに依存しないため循環の心配はないが、統一的に
# ここでまとめて解決する。
from .attack import Attack  # noqa: E402
from .detection import Detection  # noqa: E402
from .instrumentation import Instrumentation  # noqa: E402
from .structuring import Structuring  # noqa: E402
from .visualization import Visualization  # noqa: E402

Manifest.model_rebuild()

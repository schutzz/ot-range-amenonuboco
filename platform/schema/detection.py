"""マニフェストの検知層(detection)を表す Pydantic モデル。

Phase4決定事項#54: 検知プラグインはコンテナを合成せず、`host`で
`topology.assets`の資産を名前参照する。「載せる口」は本来「どこに」「何を」の
2要素であり、`host`+`source`がそれに直接対応する。

Phase4決定事項#55: Phase4で実装するプラグイン型は`sidecar`のみ。天沼矛の
取り込み経路にVectorは存在せず(Phase3決定事項#40で軽量ラッパーに置換済み)、
VRLを実行する処理系がどこにも無いため、記法ガイドα版が挙げていた
`vector-transform`型は載せる先が無い。`sidecar`型は取り込みエンジンから完全に
独立している(前身`ot-ids-verum`のSignal 6は、そのデータを誰が書いたかを
一切知らない)点を評価して一本化した。

Phase4決定事項#56・#57: 依存パッケージは`requires`として宣言で受け取り
(生の`pip install`をマニフェストに書かせない、Phase0決定事項#9)、接続情報は
`config`として受け取って環境変数で注入する。これによりプラグインは投入先の
Elasticsearchを知らないまま書ける——すなわち環境非依存のシナリオ資産になる。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, model_validator

# instrumentation.py と同じ理由で、topology.py のimportはTYPE_CHECKING配下に置く
# (topology.py が Manifest.detection の型として本モジュールをimportするため、
# トップレベルでimportし返すと循環importになる)。
if TYPE_CHECKING:
    from .topology import Topology


class DetectionPlugin(BaseModel):
    """検知ロジック1件の差し込み宣言。ロジック本体(`source`)はマニフェスト外の
    資産であり、プラットフォームは中身を一切解釈しない(Phase0決定事項#1)。
    """

    name: str
    type: Literal["sidecar"]
    # 実行主体となる資産の名前(topology.assetsに実在すること)。
    host: str
    # ロジック本体のパス(マニフェストからの相対パス、または絶対パス)。
    source: str
    # プラグインが必要とするパッケージ。生成側が導入コマンドへ合成する。
    requires: list[str] = Field(default_factory=list)
    # プラグインへ環境変数として注入される設定値。
    config: dict[str, str] = Field(default_factory=dict)


class Detection(BaseModel):
    # 評価ハーネス(正解ラベル源)は、専用フィールドではなく eval-harness ロールの
    # 通常資産 + シナリオスクリプトで表現する(決定事項#77)。当初 Phase4で
    # evaluation_harness.enabled という差し込み口フィールドを置いたが(決定事項
    # #59)、Phase5で実際に評価ハーネスを実装した際、eval-harnessロールの資産を
    # topology.assets に置き record_ground_truth.py/evaluate_signal1.py を載せる
    # 方式(検知プラグインと同型の「載せる口」)で実現でき、専用フィールドは
    # 二重表現になっていた(Phase4でattack.nodesを廃した理由=決定事項#53と同型)。
    # かつ enabled フラグは生成器から一切参照されない死んだフラグだったため
    # 削除した。将来プラットフォームが評価配線の自動化を提供する場合は、その
    # 時点で改めて設計する(YAGNI)。
    plugins: list[DetectionPlugin] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_no_duplicate_names(self) -> "Detection":
        names = [p.name for p in self.plugins]
        if len(names) != len(set(names)):
            dupes = {n for n in names if names.count(n) > 1}
            raise ValueError(
                f"duplicate plugin name(s) in detection.plugins: {sorted(dupes)}"
            )
        return self

    def plugins_for_host(self, asset_name: str) -> list[DetectionPlugin]:
        """指定資産に載るプラグイン一覧。1つのホストに複数プラグインを載せる
        構成(前身のVectorが複数transformを持っていたような形)を許す。
        """
        return [p for p in self.plugins if p.host == asset_name]


def validate_detection(detection: Detection, topology: Topology) -> None:
    """Manifest側の相互参照バリデーションから呼ばれる。`host`が実在の資産を
    指しているかを検証する(Phase1で`topology`に対して実装した相互参照検証と
    同じ扱い、決定事項#54)。
    """
    asset_names = {a.name for a in topology.assets}

    for plugin in detection.plugins:
        if plugin.host not in asset_names:
            raise ValueError(
                f"detection.plugins['{plugin.name}'].host '{plugin.host}' does not "
                f"reference a defined asset"
            )

"""マニフェストの可視化層(visualization)を表す Pydantic モデル。

Phase6決定事項#79: ネットワーク図(構造の可視化、プラットフォーム組み込み)とは
別レイヤーとして、時系列データ(検知アラート・トラフィック統計)の可視化を
外部エンジン(Grafana等)へ配線する差し込み口を定義する。

Phase6決定事項#80: `engine`は`Literal["grafana"]`で始める。可視化エンジンは
エンジンごとにプロビジョニング形式が根本的に異なる(Grafana=ファイルマウント、
Kibana=API)ため、生成側(generators/visualization/)で抽象`VisualizationEngine`
を用意しGrafanaを第1実装とする。将来のエンジン追加はこの抽象に実装を足す形。

Phase6決定事項#83: 可視化エンジン本体(Grafana server等)は`topology.assets`に
通常の資産として宣言し、ここでは`host`で名前参照するだけにする(Phase4決定事項
#53のコンテナ宣言一元化と同じ)。

Phase6決定事項#81・#86: `datasources`を省略した場合、`structuring.protocols`
由来の構造化ログindexと、検知アラートの命名規約`ot-signals-<signal>-*`
(決定事項#86)から、Elasticsearch datasourceを自動生成する(generators側の責務)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .topology import Topology


class VisualizationDatasource(BaseModel):
    """可視化エンジンが読むデータソース1件。`datasources`省略時は
    generators側が自動生成する(決定事項#81)ため、ここは明示指定時のみ使う。
    """

    name: str
    index: str
    time_field: str = "@timestamp"


class Visualization(BaseModel):
    engine: Literal["grafana"] = "grafana"
    # topology.assets の visualization-engine ロール資産を名前参照する
    # (決定事項#83、検知プラグインのhost参照・Calderaのhost参照と同じ設計)。
    host: str
    # ダッシュボード定義(JSON)はマニフェスト外のシナリオ資産(決定事項#82)。
    # プラットフォームは中身を解釈せず、読み取り専用でマウントするだけ。
    dashboards: list[str] = Field(default_factory=list)
    # 省略時は structuring.protocols + ot-signals-* から自動生成(決定事項#81)。
    datasources: list[VisualizationDatasource] = Field(default_factory=list)
    # 投入先Elasticsearch。Structuring.elasticsearch_url(Phase3決定事項#43)と
    # 同じパターンで、決め打ちにせず明示宣言できるようにする。
    elasticsearch_url: str = "http://elasticsearch:9200"

    def has_explicit_datasources(self) -> bool:
        return bool(self.datasources)


def validate_visualization(visualization: Visualization, topology: Topology) -> None:
    """Manifest側の相互参照バリデーションから呼ばれる。`host`が実在の
    visualization-engineロール資産を指しているかを検証する(決定事項#83、
    Phase4のCaldera host検証=決定事項#58と同じ方式)。
    """
    asset_names = {a.name for a in topology.assets}

    if visualization.host not in asset_names:
        raise ValueError(
            f"visualization.host '{visualization.host}' does not reference "
            f"a defined asset"
        )
    host_asset = topology.asset_by_name(visualization.host)
    if host_asset.role != "visualization-engine":
        raise ValueError(
            f"visualization.host '{visualization.host}' must have role "
            f"'visualization-engine' (has '{host_asset.role}')"
        )

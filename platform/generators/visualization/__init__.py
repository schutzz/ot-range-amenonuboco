"""可視化層(visualization)の生成パッケージ(Phase6)。

公開インターフェースは`visualization_overlay_for_asset()`のみ。呼び出し元
(generators/compose.py)は、エンジンの選択・レジストリの存在を意識しない。
"""

from __future__ import annotations

from schema import Asset, Manifest, Visualization

from .base import ComposeServiceOverlay, VisualizationEngine, VisualizationGenerationError
from .grafana import GrafanaEngine

# engineの語彙(schema/visualization.pyのLiteral["grafana"])と1対1で対応する
# レジストリ。将来エンジンを追加する場合はここに実装を足す(決定事項#80)。
_ENGINES: dict[str, VisualizationEngine] = {
    "grafana": GrafanaEngine(),
}


def visualization_overlay_for_asset(
    manifest: Manifest, visualization: Visualization | None, asset: Asset
) -> ComposeServiceOverlay | None:
    """指定資産が可視化エンジンのhostである場合、compose配線を返す。
    visualization層が未宣言、またはこの資産がhostでなければNone。
    """
    if visualization is None:
        return None
    if visualization.host != asset.name:
        return None

    engine = _ENGINES.get(visualization.engine)
    if engine is None:
        # schema側のLiteral型で既に弾かれているはずだが、レジストリと
        # スキーマの語彙が将来ズレた場合の保険。
        raise VisualizationGenerationError(
            f"unsupported visualization engine: {visualization.engine}"
        )
    return engine.wire(manifest, visualization, asset)


__all__ = [
    "ComposeServiceOverlay",
    "VisualizationEngine",
    "VisualizationGenerationError",
    "visualization_overlay_for_asset",
]

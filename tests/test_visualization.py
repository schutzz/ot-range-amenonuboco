"""可視化層(visualization)のスキーマ・生成器の回帰テスト(Phase6)。

決定事項#79〜#88で決めた設計のうち、実機を立てずに検証できる部分
(スキーマの相互参照バリデーション、`ComposeServiceOverlay`の配線内容、
datasource自動生成、ダッシュボード資産の存在チェック)を固定する。
実際にGrafanaが`configs`マウント内容を読み込むかどうかは実機検証で
別途確認済み(Phase6-Visualization.md完了条件)であり、ここでは
「生成物が正しい形をしているか」に責務を絞る。
"""

from __future__ import annotations

import copy

import pytest
import yaml
from pydantic import ValidationError

from generators.compose import ComposeGenerationError, generate_compose
from generators.visualization import VisualizationGenerationError
from renderers.network_diagram import render_network_diagram
from schema.topology import Manifest


@pytest.fixture
def base_raw(reference_manifest_path):
    return yaml.safe_load(reference_manifest_path.read_text(encoding="utf-8"))


def _validate(raw: dict) -> Manifest:
    return Manifest.model_validate(raw)


# --- スキーマの相互参照バリデーション ---------------------------------------


def test_reference_manifest_has_visualization(base_raw):
    """現行のリファレンスマニフェストはvisualization層を持つこと(基準)。"""
    manifest = _validate(base_raw)
    assert manifest.visualization is not None
    assert manifest.visualization.host == "grafana_server"


def test_visualization_layer_is_optional(base_raw):
    """visualization層は他の層と同じく任意であること(決定事項#79)。"""
    del base_raw["visualization"]
    manifest = _validate(base_raw)
    assert manifest.visualization is None


def test_reject_visualization_host_nonexistent(base_raw):
    base_raw["visualization"]["host"] = "nonexistent"
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_visualization_host_wrong_role(base_raw):
    """visualization.hostはvisualization-engineロールの資産のみ指せる
    (決定事項#83、Caldera host検証=決定事項#58と同じ方式)。"""
    base_raw["visualization"]["host"] = "cc_scada_master"
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_unsupported_engine(base_raw):
    """engineはPhase6時点でLiteral["grafana"]のみ(決定事項#80)。"""
    base_raw["visualization"]["engine"] = "kibana"
    with pytest.raises(ValidationError):
        _validate(base_raw)


# --- generators/visualization: ComposeServiceOverlayの配線内容 --------------


@pytest.fixture
def compose(reference_manifest, presets):
    return generate_compose(reference_manifest, presets)


def test_compose_wires_visualization_engine_service(compose):
    svc = compose["services"]["grafana_server"]
    assert svc["ports"] == ["3000:3000"]
    assert "GF_AUTH_ANONYMOUS_ENABLED=true" in svc["environment"]
    assert "GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer" in svc["environment"]


def test_compose_top_level_configs_are_globally_unique(compose):
    """configのキーは`{資産名}_{ローカル名}`でグローバル一意化される
    (compose.py側の責務、決定事項#84)。"""
    assert "grafana_server_datasources" in compose["configs"]
    assert "grafana_server_dashboards-provider" in compose["configs"]
    svc_configs = {c["source"] for c in compose["services"]["grafana_server"]["configs"]}
    assert svc_configs == set(compose["configs"].keys()) & {
        "grafana_server_datasources",
        "grafana_server_dashboards-provider",
    }


def test_datasources_config_targets_grafana_provisioning_path(compose):
    entries = {
        c["source"]: c["target"] for c in compose["services"]["grafana_server"]["configs"]
    }
    assert (
        entries["grafana_server_datasources"]
        == "/etc/grafana/provisioning/datasources/datasources.yml"
    )
    assert (
        entries["grafana_server_dashboards-provider"]
        == "/etc/grafana/provisioning/dashboards/dashboards.yml"
    )


def test_auto_datasource_combines_structuring_and_signals_pattern(compose):
    """datasources省略時、structuring.protocols由来のindexと
    ot-signals-*規約(決定事項#86)を束ねた1つのdatasourceが自動生成される
    (決定事項#81)。"""
    content = compose["configs"]["grafana_server_datasources"]["content"]
    doc = yaml.safe_load(content)
    index_pattern = doc["datasources"][0]["jsonData"]["index"]
    assert "ot-logs-http-*" in index_pattern
    assert "ot-logs-dnp3-*" in index_pattern
    assert "ot-signals-*" in index_pattern
    assert doc["datasources"][0]["jsonData"]["timeField"] == "@timestamp"
    assert doc["datasources"][0]["isDefault"] is True


def test_dashboard_provider_yaml_points_at_provisioning_dir(compose):
    content = compose["configs"]["grafana_server_dashboards-provider"]["content"]
    doc = yaml.safe_load(content)
    assert doc["providers"][0]["options"]["path"] == "/etc/grafana/provisioning/dashboards"


def test_dashboard_json_bind_mounted_read_only(compose, reference_manifest):
    """ダッシュボードJSONはプラットフォームが解釈せず、読み取り専用マウント
    するだけの外部シナリオ資産であること(決定事項#82)。"""
    host_path = reference_manifest.resolve_path(
        reference_manifest.visualization.dashboards[0]
    )
    expected = f"{host_path.as_posix()}:/etc/grafana/provisioning/dashboards/{host_path.name}:ro"
    assert expected in compose["services"]["grafana_server"]["volumes"]


def test_no_visualization_layer_means_no_grafana_overlay(
    base_raw, presets, reference_manifest_path
):
    """visualization層が無ければ、可視化関連のconfigs/environmentも一切
    生成されないこと(層の任意性)。"""
    del base_raw["visualization"]
    base_raw["topology"]["assets"] = [
        a for a in base_raw["topology"]["assets"] if a["name"] != "grafana_server"
    ]
    manifest = _validate(base_raw)
    manifest.source_dir = reference_manifest_path.parent
    compose = generate_compose(manifest, presets)
    assert "configs" not in compose
    assert "grafana_server" not in compose["services"]


def test_missing_dashboard_file_raises_generation_error(
    base_raw, presets, reference_manifest_path
):
    """存在しないダッシュボードJSONを宣言したら生成時に弾かれること
    (プラットフォームは中身を解釈しないが、存在チェックはする)。"""
    base_raw["visualization"]["dashboards"] = [
        "../scenarios/legacy-power-grid-signals/dashboards/nonexistent.json"
    ]
    manifest = _validate(base_raw)
    manifest.source_dir = reference_manifest_path.parent
    with pytest.raises(ComposeGenerationError):
        generate_compose(manifest, presets)


def test_explicit_datasources_override_auto_generation(
    base_raw, presets, reference_manifest_path
):
    """datasourcesを明示すると自動生成をスキップすること(決定事項#81)。"""
    base_raw["visualization"]["datasources"] = [
        {"name": "Custom", "index": "custom-index-*", "time_field": "@timestamp"}
    ]
    manifest = _validate(base_raw)
    manifest.source_dir = reference_manifest_path.parent
    compose = generate_compose(manifest, presets)
    doc = yaml.safe_load(compose["configs"]["grafana_server_datasources"]["content"])
    assert len(doc["datasources"]) == 1
    assert doc["datasources"][0]["name"] == "Custom"
    assert doc["datasources"][0]["jsonData"]["index"] == "custom-index-*"


# --- renderers/network_diagram: 可視化エンジンの反映 -------------------------


def test_network_diagram_shows_visualization_engine_role_color(reference_manifest):
    html = render_network_diagram(reference_manifest)
    assert "#e0a63c" in html
    assert 'fill="#888888"' not in html


def test_network_diagram_shows_visualization_tooltip(reference_manifest):
    html = render_network_diagram(reference_manifest)
    assert "可視化エンジン: Grafana" in html


def test_network_diagram_info_panel_lists_visualization(reference_manifest):
    html = render_network_diagram(reference_manifest)
    assert "可視化（grafana）" in html

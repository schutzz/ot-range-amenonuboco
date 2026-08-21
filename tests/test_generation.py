"""生成器(compose / network_diagram)の出力に関する回帰テスト。

「生成物が構造として正しいか」「生成されたシェルコマンドが構文として
正しいか」を自動化する。後者は罠#010・#020(バックグラウンド起動の
`&`が`&&`結合と衝突する)を恒久的に検出するための守りであり、実機で
docker compose up する前に潰せるようにする。
"""

from __future__ import annotations

import shlex
import subprocess

import pytest

from generators.compose import generate_compose, dump_compose_yaml
from renderers.network_diagram import render_network_diagram


@pytest.fixture
def compose(reference_manifest, presets):
    return generate_compose(reference_manifest, presets)


def test_compose_has_all_assets(reference_manifest, compose):
    """全資産がサービスとして生成されること。"""
    asset_names = {a.name for a in reference_manifest.topology.assets}
    assert set(compose["services"].keys()) == asset_names


def test_compose_has_all_segments_as_networks(reference_manifest, compose):
    segment_names = {s.name for s in reference_manifest.topology.segments}
    assert set(compose["networks"].keys()) == segment_names


def test_compose_yaml_dumps_without_error(compose):
    text = dump_compose_yaml(compose)
    assert "services:" in text
    assert "networks:" in text


def _extract_inner_command(cmd: str) -> str:
    """`sh -c "..."` 形式のcommandから中身を取り出し、Compose用の`$$`を
    シェルの`$`へ戻す。"""
    tokens = shlex.split(cmd)
    return tokens[-1].replace("$$", "$")


def test_all_generated_commands_are_valid_shell(compose):
    """生成された全サービスのcommandが、シェル構文として正しいこと
    (罠#010・#020の再発防止)。"""
    failures = []
    for name, svc in compose["services"].items():
        cmd = svc.get("command")
        if not cmd:
            continue
        inner = _extract_inner_command(cmd)
        result = subprocess.run(
            ["sh", "-n", "-c", inner], capture_output=True, text=True
        )
        if result.returncode != 0:
            failures.append(f"{name}: {result.stderr.strip()}")
    assert not failures, "shell syntax errors:\n" + "\n".join(failures)


def test_generated_commands_escape_dollar_for_compose(compose):
    """シェル変数を含むcommandは、Compose補間対策で`$$`にエスケープ済み
    であること(決定事項#33、罠#007)。裸の単一`$`が残っていないこと。"""
    for name, svc in compose["services"].items():
        cmd = svc.get("command")
        if not cmd or "$" not in cmd:
            continue
        # `$$`を除去した後に単一の`$`が残っていたら、エスケープ漏れ。
        stripped = cmd.replace("$$", "")
        assert "$" not in stripped, f"{name}: unescaped $ remains: {cmd}"


def test_detection_infra_without_command_is_untouched(reference_manifest, compose):
    """overrides.command も自前起動も無い資産(vector/elasticsearch)には
    command が生成されないこと(決定事項#22、ベースイメージの尊重)。"""
    # elasticsearch は overrides.environment のみで command 無し。
    assert "command" not in compose["services"]["elasticsearch"]
    assert "command" not in compose["services"]["vector"]


def test_network_diagram_renders_all_assets(reference_manifest):
    """ネットワーク図に全資産のノードが描画されること。"""
    html = render_network_diagram(reference_manifest)
    n_nodes = html.count('class="asset-node"')
    assert n_nodes == len(reference_manifest.topology.assets)


def test_network_diagram_no_fallback_color(reference_manifest):
    """フォールバック色(#888888)が使われていないこと=全ロールに色定義が
    あること(罠#014の再発防止)。"""
    html = render_network_diagram(reference_manifest)
    assert 'fill="#888888"' not in html


def test_network_diagram_is_self_contained(reference_manifest):
    """自己完結HTML(外部CDN読み込みが無いこと、Phase0決定事項#6)。"""
    html = render_network_diagram(reference_manifest)
    assert "http://" not in html.replace("http://www.w3.org", "")  # SVG名前空間は除外
    assert "src=" not in html


def test_structurer_has_cgroups_limits(compose):
    """structurer資産に Cgroups リソース制限 (deploy.resources.limits) が設定されていること(Phase 9.5 決定事項#140)。"""
    structurer_svc = compose["services"]["log_structurer"]
    assert "deploy" in structurer_svc
    limits = structurer_svc["deploy"]["resources"]["limits"]
    assert limits["cpus"] == "1.0"
    assert limits["memory"] == "512M"


def test_structurer_resource_limits_can_be_overridden(presets, repo_root):
    """負荷計測用マニフェストは安全側既定値を明示的に上書きできる。"""
    from schema import load_manifest

    manifest = load_manifest(repo_root / "manifests" / "stress-test-reference.yaml")
    compose = generate_compose(manifest, presets)
    limits = compose["services"]["log_structurer"]["deploy"]["resources"]["limits"]
    assert limits == {"cpus": "4.0", "memory": "512M"}

"""`manifests/` に置かれた全マニフェストを対象にした横断テスト。

Phase 9 で分野を15枚まで増やすにあたり、「1枚ずつ手で確認する」運用は
現実的でなくなった。ここで全枚数に同じ検査を課すことで、新しい分野を
足す作業が「テストを通す」作業になり、書き漏らしが自動で見つかるようにする。

既存の tests/test_generation.py は電力リファレンス固有の表明（vector や
elasticsearch に command が生成されないこと等）を含むため残し、本ファイルは
**どの分野のマニフェストにも共通して成り立つべき性質**だけを扱う。

検査する性質は、いずれも「宣言としては通るが実機で初めて壊れる」類を
実機を立てずに潰すためのもの（Phase5.5以来の方針）。
"""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path

import pytest

from generators.compose import dump_compose_yaml, generate_compose
from generators.mirroring import generate_mirroring_commands
from renderers.network_diagram import render_network_diagram
from schema import load_manifest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_DIR = _REPO_ROOT / "manifests"

# 生成物(*.docker-compose.yml 等)は .gitignore 対象だが、手元に残っている
# ことがあるため除外する。マニフェストの本体は *-reference.yaml 命名。
_MANIFEST_PATHS = sorted(
    p
    for p in _MANIFEST_DIR.glob("*.yaml")
    if not p.name.endswith(".docker-compose.yml")
    and ".generated." not in p.name
)


def _ids(paths):
    return [p.stem for p in paths]


assert _MANIFEST_PATHS, "manifests/ にマニフェストが1枚も見つからない"


@pytest.fixture(params=_MANIFEST_PATHS, ids=_ids(_MANIFEST_PATHS))
def manifest(request):
    return load_manifest(request.param)


@pytest.fixture
def compose_for(manifest, presets):
    return generate_compose(manifest, presets)


# --- スキーマ・生成の成立 ----------------------------------------------------


def test_manifest_loads(manifest):
    """スキーマ検証を通ること（相互参照・CIDR・IP重複等を含む）。"""
    assert manifest.topology.segments, "セグメントが空"
    assert manifest.topology.assets, "資産が空"


def test_compose_has_all_assets_and_segments(manifest, compose_for):
    """全資産がサービスに、全セグメントがネットワークになること。"""
    assert set(compose_for["services"]) == {a.name for a in manifest.topology.assets}
    assert set(compose_for["networks"]) == {s.name for s in manifest.topology.segments}


def test_compose_yaml_dumps(compose_for):
    text = dump_compose_yaml(compose_for)
    assert "services:" in text and "networks:" in text


# --- 生成コマンドの健全性 ----------------------------------------------------


def _inner_command(cmd: str) -> str:
    """`sh -c "..."` の中身を取り出し、Compose用の `$$` をシェルの `$` へ戻す。"""
    return shlex.split(cmd)[-1].replace("$$", "$")


def test_generated_commands_are_valid_shell(compose_for):
    """全サービスの起動コマンドがシェル構文として正しいこと。

    バックグラウンド起動の `&` が `&&` 結合と衝突する類の不具合を、
    実機で docker compose up する前に潰す。
    """
    failures = []
    for name, svc in compose_for["services"].items():
        cmd = svc.get("command")
        if not cmd:
            continue
        result = subprocess.run(
            ["sh", "-n", "-c", _inner_command(cmd)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            failures.append(f"{name}: {result.stderr.strip()}")
    assert not failures, "shell syntax errors:\n" + "\n".join(failures)


def test_generated_commands_escape_dollar(compose_for):
    """シェル変数を含むコマンドが Compose の変数補間対策で `$$` になっていること。"""
    for name, svc in compose_for["services"].items():
        cmd = svc.get("command")
        if not cmd or "$" not in cmd:
            continue
        assert "$" not in cmd.replace("$$", ""), f"{name}: unescaped $ remains"


def test_no_double_quotes_in_override_commands(manifest):
    """資産の overrides.command に二重引用符が無いこと。

    生成物では起動コマンドが最終的に `sh -c "..."` で包まれるため、中に
    二重引用符があると包みが破れ、コンテナ内で構文エラーになる。YAMLとしても
    スキーマとしても妥当なので宣言時には弾けず、実機で初めて壊れる。
    """
    offenders = [
        a.name
        for a in manifest.topology.assets
        if a.overrides.command and '"' in a.overrides.command
    ]
    assert not offenders, (
        f"overrides.command に二重引用符を含む資産: {offenders}. "
        "単一引用符へ置き換えること"
    )


# --- 計装・構造化の前提が揃っていること --------------------------------------


def test_mirroring_commands_generate(manifest):
    """計装層を宣言しているなら、ミラーリング設定が生成できること。

    ＝ゲートウェイが全観測対象セグメントと mirror_to に静的IPを持つこと。
    これを満たさないマニフェストは `cli.py provision` の時点で落ちる。
    """
    if manifest.instrumentation is None:
        pytest.skip("instrumentation 層を宣言していない")
    commands = generate_mirroring_commands(manifest.topology, manifest.instrumentation)
    assert commands, "ミラーリングコマンドが空"


def test_structuring_has_structurer_asset(manifest):
    """構造化層を宣言しているなら、実行主体（structurer）が存在すること。

    スキーマ側でも弾いているが、ここでも表明しておく（15分野を横断して
    「宣言したのに tshark が起動しない」状態が無いことの保証）。
    """
    if manifest.structuring is None or not manifest.structuring.protocols:
        pytest.skip("structuring 層を宣言していない")
    structurers = [a for a in manifest.topology.assets if a.role == "structurer"]
    assert structurers, "structuring を宣言しているのに structurer 資産が無い"


def test_structurer_has_static_ip_on_mirror_segment(manifest):
    """structurer が観測用セグメント上に静的IPを持つこと。

    自分のIPからインターフェース名を解決する設計のため、動的割当では
    構造化パイプラインの生成時に落ちる。
    """
    if manifest.structuring is None or not manifest.structuring.protocols:
        pytest.skip("structuring 層を宣言していない")
    mirror_to = manifest.instrumentation.mirror_to
    for asset in manifest.topology.assets:
        if asset.role != "structurer":
            continue
        assert asset.ip_on_segment(mirror_to), (
            f"structurer '{asset.name}' が観測用セグメント '{mirror_to}' 上に"
            "静的IPを持っていない"
        )


def test_gateway_is_l3_router_and_reaches_observed_segments(manifest):
    """ゲートウェイが l3-router であり、観測対象すべてに接続していること。"""
    if manifest.topology.routing is None:
        pytest.skip("routing を宣言していない")
    gateway = manifest.topology.asset_by_name(manifest.topology.routing.gateway)
    assert gateway.role == "l3-router"

    if manifest.instrumentation is None:
        return
    connected = {n.segment for n in gateway.networks}
    observed = {s.name for s in manifest.instrumentation.observed_segments(manifest.topology)}
    missing = observed - connected
    assert not missing, (
        f"ゲートウェイ '{gateway.name}' が観測対象セグメントに接続していない: "
        f"{sorted(missing)}"
    )


def test_excluded_segments_are_really_unobserved(manifest):
    """exclude されたセグメントが観測対象に含まれていないこと。

    観測境界を持つ分野（一部が構造的に観測できない器）では、死角の宣言が
    実態と一致していることが主張の核になるため、明示的に表明しておく。
    """
    if manifest.instrumentation is None or not manifest.instrumentation.exclude:
        pytest.skip("exclude を使っていない")
    observed = {s.name for s in manifest.instrumentation.observed_segments(manifest.topology)}
    for name in manifest.instrumentation.exclude:
        assert name not in observed, f"exclude したはずの '{name}' が観測対象に含まれる"


def test_assets_on_unrouted_segments_have_no_command(manifest):
    """ゲートウェイが接続していないセグメント上の資産は、起動コマンドを
    持たないこと（Phase9 Stage4の観測境界を持つ器）。

    ゲートウェイの無いセグメント＝エアギャップの表現であり、そこに置く資産に
    他セグメントへの経路は存在しない。にもかかわらず overrides.command を
    書くと、生成器が「自前の起動コマンドを持つ資産にはルーティングを与える」
    規則に従って経由先ゲートウェイIPを探し、見つからず生成時に落ちる。

    つまりこの表明が破れているマニフェストは `generate_compose` の時点で
    既に落ちているが、**なぜ落ちたのかが分かる形で**残しておく。
    """
    if manifest.topology.routing is None:
        pytest.skip("routing を宣言していない")
    gateway = manifest.topology.asset_by_name(manifest.topology.routing.gateway)
    reachable = {n.segment for n in gateway.networks}

    offenders = []
    for asset in manifest.topology.assets:
        if asset.name == gateway.name or not asset.networks:
            continue
        if asset.networks[0].segment in reachable:
            continue
        if asset.overrides.command:
            offenders.append(asset.name)
    assert not offenders, (
        f"ゲートウェイ非接続セグメント上の資産が overrides.command を持つ: "
        f"{offenders}. 経路が存在しない以上、イメージ側のCMDで動かすこと"
    )


def test_excluded_segments_render_as_blind_spots(manifest):
    """exclude したセグメントが、図の上で死角として描かれること。

    「観測できない領域を隠さず、最も目立つ形で描く」という本プロジェクトの
    設計思想（Phase0決定事項#6）が、実際の生成物で成立していることの表明。
    """
    if manifest.instrumentation is None or not manifest.instrumentation.exclude:
        pytest.skip("exclude を使っていない")
    html = render_network_diagram(manifest)
    observed = {s.name for s in manifest.instrumentation.observed_segments(manifest.topology)}

    for name in manifest.instrumentation.exclude:
        titles = re.findall(r"<title>([^<]*)</title>", html)
        matched = [t for t in titles if t.startswith(name + " ")]
        assert matched, f"死角セグメント '{name}' が図に現れていない"
        assert all("観測外" in t for t in matched), (
            f"死角セグメント '{name}' が観測外として描かれていない: {matched}"
        )

    # 観測対象のセグメントが巻き添えで死角扱いになっていないこと（誤検知の防止）。
    for name in observed:
        titles = [
            t
            for t in re.findall(r"<title>([^<]*)</title>", html)
            if t.startswith(name + " ")
        ]
        assert all("観測外" not in t for t in titles), (
            f"観測対象のセグメント '{name}' が死角として描かれている: {titles}"
        )


# --- ローカルビルド参照（image にパスを書く記法） ----------------------------


def test_local_path_image_becomes_build_context(manifest, compose_for):
    """`image` が `./`・`../` 始まりの資産は、生成物で `build:` になること。

    独自のプロトコル実装をコンテナ化して資産に載せるための記法。既存機能
    だが利用例が無く未検証だったため、実際に使い始めるにあたり表明する。
    """
    for asset in manifest.topology.assets:
        svc = compose_for["services"][asset.name]
        if asset.image.startswith("./") or asset.image.startswith("../"):
            assert svc.get("build") == asset.image, (
                f"{asset.name}: ローカルパス指定が build: になっていない"
            )
            assert "image" not in svc, f"{asset.name}: build と image が併存している"
        else:
            assert svc.get("image") == asset.image
            assert "build" not in svc


# --- ネットワーク図 ----------------------------------------------------------


def test_diagram_renders_all_assets(manifest):
    html = render_network_diagram(manifest)
    assert html.count('class="asset-node"') == len(manifest.topology.assets)


def test_diagram_has_no_fallback_color(manifest):
    """未定義ロールのフォールバック色が使われていないこと。"""
    html = render_network_diagram(manifest)
    assert 'fill="#888888"' not in html


def test_diagram_is_self_contained(manifest):
    """外部読み込みの無い自己完結HTMLであること。"""
    html = render_network_diagram(manifest)
    assert "http://" not in html.replace("http://www.w3.org", "")
    assert "src=" not in html

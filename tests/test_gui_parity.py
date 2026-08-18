"""GUI(JS)とプラットフォーム(Python)の検証ロジックのパリティテスト。

GUIはクライアントサイド完結のためPydanticを呼べず、構造検証をJSへ移植して
いる(Phase8決定事項#117)。移植した以上、両者がズレる余地が原理的に残る。
特に危険なのは「GUIが通したものをPythonが弾く」向きの乖離で、ユーザーから
見ると『GUIでエラーが無かったのに provision したら落ちた』になる。

ここでは不正なマニフェストの一覧に対し、Python側(Pydantic)とJS側
(`node` で validate.js を実行)の双方が拒否することを表明する(決定事項#122)。
`node` が無い環境ではスキップする(GitHub Actionsのubuntuランナーには標準で
入っているため、CIでは実際に走る)。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from schema.topology import Manifest
from tools.gen_gui_vocab import manifest_to_model

_NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(
    _NODE is None, reason="node が無い環境ではJS側の検証を実行できない"
)


# GUIのJSを node 上で読み、モデルを検証して結果をJSONで返すハーネス。
# gui/ の各ファイルは window へ生やすだけのスクリプトなので、擬似的な
# window を用意して順に評価する(ブラウザでの読み込み順と同じ)。
_HARNESS = textwrap.dedent(
    """
    const fs = require('fs');
    const path = require('path');
    const vm = require('vm');

    const guiDir = process.argv[2];
    const modelPath = process.argv[3];

    const sandbox = { window: {}, console };
    sandbox.globalThis = sandbox;
    vm.createContext(sandbox);

    for (const f of ['vocab.js', 'samples.js', 'model.js', 'validate.js', 'diagram.js', 'yaml.js']) {
      vm.runInContext(fs.readFileSync(path.join(guiDir, f), 'utf8'), sandbox, { filename: f });
    }

    const W = sandbox.window;
    const raw = JSON.parse(fs.readFileSync(modelPath, 'utf8'));
    const model = W.AmenonubocoModel.normalize(raw);
    const result = W.AmenonubocoValidate.validate(model);

    // レイアウト計算の結果も返す(Python版との座標一致を検証するため)
    const round3 = (v) => Math.round(v * 1000) / 1000;
    let layout = null;
    if ((model.topology.segments || []).length) {
      const heights = W.AmenonubocoDiagram.segmentBoxHeights(model.topology);
      const geo = W.AmenonubocoDiagram.canvasGeometry(model.topology.segments, heights);
      const pos = W.AmenonubocoDiagram.segmentPositions(
        model.topology.segments, geo.center, geo.radius);
      const cov = W.AmenonubocoDiagram.coverage(model);
      layout = {
        viewW: round3(geo.viewW),
        viewH: round3(geo.viewH),
        radius: round3(geo.radius),
        center: geo.center.map(round3),
        heights: Object.fromEntries(
          Object.entries(heights).map(([k, v]) => [k, round3(v)])),
        positions: Object.fromEntries(
          Object.entries(pos).map(([k, v]) => [k, v.map(round3)])),
        observed: [...cov.observed].sort(),
        mirrorTo: cov.mirrorTo,
      };
    }

    process.stdout.write(JSON.stringify({
      ok: result.ok,
      errors: result.errors.map((e) => e.message),
      warnings: result.warnings.map((e) => e.message),
      yaml: W.AmenonubocoYaml.dump(model),
      layout,
    }));
    """
)


@pytest.fixture(scope="module")
def harness_path(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("gui") / "harness.cjs"
    path.write_text(_HARNESS, encoding="utf-8")
    return path


def run_js_validate(harness_path: Path, gui_dir: Path, model: dict) -> dict:
    """JS側の検証を実行し、結果を返す。"""
    model_file = harness_path.parent / "model.json"
    model_file.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [_NODE, str(harness_path), str(gui_dir), str(model_file)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, f"node の実行に失敗:\n{proc.stderr}"
    return json.loads(proc.stdout)


def python_accepts(model: dict) -> bool:
    try:
        Manifest.model_validate(model)
    except ValidationError:
        return False
    return True


@pytest.fixture(scope="module")
def gui_dir(request) -> Path:
    return Path(request.config.rootpath) / "gui"


@pytest.fixture
def base_model(reference_manifest) -> dict:
    """電力リファレンスを、GUIの編集モデル形式で返す(改変の土台)。"""
    return manifest_to_model(reference_manifest)


# --- 正常系 -----------------------------------------------------------------


def test_reference_accepted_by_both(harness_path, gui_dir, base_model):
    """リファレンスは両者とも受理すること(基準)。"""
    assert python_accepts(base_model)
    result = run_js_validate(harness_path, gui_dir, base_model)
    assert result["ok"], f"JS側が誤って拒否した: {result['errors']}"
    assert not result["warnings"], f"想定外の警告: {result['warnings']}"


# --- 異常系: 両者が拒否すべきもの --------------------------------------------
#
# 各ケースは base_model を1点だけ壊す。Python(Pydantic)とJS(validate.js)の
# 双方が拒否することを確認する。


def _mutate_duplicate_segment_name(m: dict) -> None:
    m["topology"]["segments"].append(
        {"name": "cc_lan", "cidr": "10.9.0.0/24", "kind": "it-core"}
    )


def _mutate_duplicate_asset_name(m: dict) -> None:
    m["topology"]["assets"].append(json.loads(json.dumps(m["topology"]["assets"][1])))


def _mutate_undefined_segment_reference(m: dict) -> None:
    m["topology"]["assets"][1]["networks"].append(
        {"segment": "no-such-segment", "ip": None}
    )


def _mutate_double_connection(m: dict) -> None:
    seg = m["topology"]["assets"][1]["networks"][0]["segment"]
    m["topology"]["assets"][1]["networks"].append({"segment": seg, "ip": None})


def _mutate_ip_outside_cidr(m: dict) -> None:
    m["topology"]["assets"][1]["networks"][0]["ip"] = "192.0.2.77"


def _mutate_duplicate_ip(m: dict) -> None:
    assets = m["topology"]["assets"]
    donor = next(a for a in assets if a["name"] == "cc_scada_master")
    receiver = next(a for a in assets if a["name"] == "historian")
    receiver["networks"][0]["ip"] = donor["networks"][0]["ip"]


def _mutate_invalid_cidr(m: dict) -> None:
    m["topology"]["segments"][0]["cidr"] = "not-a-cidr"


def _mutate_cidr_with_host_bits(m: dict) -> None:
    # ipaddress.ip_network(..., strict=True) はホスト部が0でないCIDRを拒否する
    m["topology"]["segments"][0]["cidr"] = "10.1.10.5/24"


def _mutate_invalid_ip(m: dict) -> None:
    m["topology"]["assets"][1]["networks"][0]["ip"] = "10.1.10.999"


def _mutate_gateway_not_router(m: dict) -> None:
    m["topology"]["routing"]["gateway"] = "cc_scada_master"


def _mutate_gateway_missing_asset(m: dict) -> None:
    m["topology"]["routing"]["gateway"] = "no-such-asset"


def _mutate_mirror_to_undefined(m: dict) -> None:
    m["instrumentation"]["mirror_to"] = "no-such-segment"


def _mutate_exclude_undefined(m: dict) -> None:
    m["instrumentation"]["exclude"] = ["no-such-segment"]


def _mutate_duplicate_protocol(m: dict) -> None:
    m["structuring"]["protocols"].append(
        {"name": "dnp3", "output_index": "ot-logs-dnp3-*"}
    )


def _mutate_structuring_without_instrumentation(m: dict) -> None:
    m["instrumentation"] = None


def _mutate_asset_without_networks(m: dict) -> None:
    m["topology"]["assets"][1]["networks"] = []


def _mutate_structuring_without_structurer(m: dict) -> None:
    # 構造化パイプラインの実行主体が居ないと、protocols を宣言しても
    # tshark が1つも起動しない（生成器が黙って空のコマンド列を返す）。
    m["topology"]["assets"] = [
        a for a in m["topology"]["assets"] if a["role"] != "structurer"
    ]


REJECT_CASES = {
    "duplicate_segment_name": _mutate_duplicate_segment_name,
    "duplicate_asset_name": _mutate_duplicate_asset_name,
    "undefined_segment_reference": _mutate_undefined_segment_reference,
    "double_connection_to_same_segment": _mutate_double_connection,
    "ip_outside_segment_cidr": _mutate_ip_outside_cidr,
    "duplicate_ip_on_segment": _mutate_duplicate_ip,
    "invalid_cidr": _mutate_invalid_cidr,
    "cidr_with_host_bits_set": _mutate_cidr_with_host_bits,
    "invalid_ip": _mutate_invalid_ip,
    "gateway_is_not_l3_router": _mutate_gateway_not_router,
    "gateway_references_missing_asset": _mutate_gateway_missing_asset,
    "mirror_to_undefined_segment": _mutate_mirror_to_undefined,
    "exclude_undefined_segment": _mutate_exclude_undefined,
    "duplicate_protocol_name": _mutate_duplicate_protocol,
    "structuring_without_instrumentation": _mutate_structuring_without_instrumentation,
    "structuring_without_structurer_asset": _mutate_structuring_without_structurer,
    "asset_without_networks": _mutate_asset_without_networks,
}


@pytest.mark.parametrize("case", sorted(REJECT_CASES))
def test_both_sides_reject(harness_path, gui_dir, base_model, case):
    """Python側とJS側の双方が同じ不正入力を拒否すること。

    片方だけ通ると、GUIの表示と実際の provision の結果が食い違う。特に
    「JSは通したがPythonが弾く」向きは、ユーザーから見て原因が追えない。
    """
    REJECT_CASES[case](base_model)

    py_ok = python_accepts(base_model)
    js = run_js_validate(harness_path, gui_dir, base_model)

    assert not py_ok, f"[{case}] Python側が拒否しなかった"
    assert not js["ok"], (
        f"[{case}] JS側が拒否しなかった（GUIで気づけないままYAMLが出力される）"
    )


# --- 警告: Pydanticは通すが provision で落ちるもの ---------------------------


def test_warns_when_gateway_lacks_static_ip(harness_path, gui_dir, base_model):
    """ゲートウェイの静的IP不足を、JS側が警告として先出しすること。

    これはPydanticの検証を通り、`cli.py provision` の実行時に初めて
    MirroringGenerationError で落ちる。エラーの出る場所と原因の場所が
    離れていて初見では解きにくいため、GUIで防ぐ価値が高い。
    """
    gateway = next(
        a for a in base_model["topology"]["assets"] if a["role"] == "l3-router"
    )
    # 観測対象セグメントの1つから静的IPを外す
    target = next(n for n in gateway["networks"] if n["segment"] == "sub_b_lan")
    target["ip"] = None

    # Pydanticは通す（宣言としては妥当）
    assert python_accepts(base_model)

    js = run_js_validate(harness_path, gui_dir, base_model)
    assert js["ok"], "エラーではなく警告として扱うこと"
    assert any("sub_b_lan" in w for w in js["warnings"]), (
        f"静的IP不足の警告が出ていない: {js['warnings']}"
    )

    # 実際にプラットフォーム側が生成時に落ちることの確認（警告が的外れでないこと）
    from generators.mirroring import MirroringGenerationError, generate_mirroring_commands

    manifest = Manifest.model_validate(base_model)
    with pytest.raises(MirroringGenerationError):
        generate_mirroring_commands(manifest.topology, manifest.instrumentation)


def test_warns_on_double_quotes_in_command(harness_path, gui_dir, base_model):
    """overrides.command 中の二重引用符を、JS側が警告として先出しすること。

    生成される docker-compose.yml では起動コマンドが `sh -c "..."` に包まれる
    ため、中に二重引用符があると包みが破れてコンテナ内で構文エラーになる。
    YAMLとしてもスキーマとしても妥当なので宣言時には弾けず、
    `docker compose up` して初めて壊れる。

    GUIは overrides.command を自由入力の欄として提供する以上、この規約を
    知らない利用者が普通に踏む。プラットフォーム側の制約をGUIが先回りして
    伝える必要がある。
    """
    target = base_model["topology"]["assets"][1]
    target["overrides"]["command"] = 'python3 -c "print(1)"'

    # Pydanticは通す（宣言としては妥当）
    assert python_accepts(base_model)

    js = run_js_validate(harness_path, gui_dir, base_model)
    assert js["ok"], "エラーではなく警告として扱うこと"
    assert any("二重引用符" in w for w in js["warnings"]), (
        f"二重引用符の警告が出ていない: {js['warnings']}"
    )


def test_single_quoted_command_does_not_warn(harness_path, gui_dir, base_model):
    """単一引用符で書かれたコマンドには警告を出さないこと（誤検知の防止）。"""
    target = base_model["topology"]["assets"][1]
    target["overrides"]["command"] = "python3 -c 'print(1)'"

    js = run_js_validate(harness_path, gui_dir, base_model)
    assert not any("二重引用符" in w for w in js["warnings"])


# --- レイアウト計算のパリティ ------------------------------------------------


@pytest.mark.parametrize(
    "stem",
    [
        "power-grid-reference",
        "water-utility-reference",
        "manufacturing-plant-reference",
    ],
)
def test_layout_matches_python_renderer(harness_path, gui_dir, repo_root, stem):
    """GUIのプレビューが、Python版レンダラと同じ座標を出すこと。

    円周半径・箱の高さ・各セグメントの中心座標・観測カバレッジまで一致を見る。
    これらはいずれも罠#015・#016・#021・#024で繰り返し調整してきた値であり、
    JS側にハードコードすると必ずズレる。vocab.js 経由で定数を共有している
    ことの実効性を、計算結果の一致という形で確認する。

    7セグメント20資産の電力リファレンスは、動的半径・動的箱高さの両方が
    効く最も重いケースにあたる。
    """
    from renderers import network_diagram as nd
    from schema import load_manifest

    manifest = load_manifest(repo_root / "manifests" / f"{stem}.yaml")
    topology = manifest.topology

    heights = nd._segment_box_heights(topology)
    view_w, view_h, center, radius = nd._canvas_geometry(topology.segments, heights)
    positions = nd._segment_positions(topology.segments, center, radius)
    observed, mirror_to = nd._coverage(manifest)

    expected = {
        "viewW": round(view_w, 3),
        "viewH": round(view_h, 3),
        "radius": round(radius, 3),
        "center": [round(center[0], 3), round(center[1], 3)],
        "heights": {k: round(v, 3) for k, v in heights.items()},
        "positions": {
            k: [round(v[0], 3), round(v[1], 3)] for k, v in positions.items()
        },
        "observed": sorted(observed),
        "mirrorTo": mirror_to,
    }

    js = run_js_validate(harness_path, gui_dir, manifest_to_model(manifest))
    assert js["layout"] == expected


# --- YAML出力の往復 ---------------------------------------------------------


@pytest.mark.parametrize(
    "stem",
    [
        "power-grid-reference",
        "water-utility-reference",
        "manufacturing-plant-reference",
    ],
)
def test_exported_yaml_round_trips(harness_path, gui_dir, repo_root, tmp_path, stem):
    """GUIが書き出したYAMLが、Python側で読めて元と同じ3層になること。

    GUIの出力がそのまま `cli.py provision` に通ることの、自動化された裏付け。
    """
    from schema import load_manifest

    original = load_manifest(repo_root / "manifests" / f"{stem}.yaml")
    model = manifest_to_model(original)

    js = run_js_validate(harness_path, gui_dir, model)
    assert js["ok"], f"JS側が拒否した: {js['errors']}"

    exported = tmp_path / f"{stem}.generated.yaml"
    exported.write_text(js["yaml"], encoding="utf-8")

    reloaded = load_manifest(exported)

    def snapshot(m):
        t = m.topology
        return (
            m.api_version,
            m.kind,
            m.metadata.name,
            m.metadata.description,
            [(s.name, s.cidr, s.kind) for s in t.segments],
            [
                (
                    a.name,
                    a.role,
                    a.image,
                    [(n.segment, n.ip) for n in a.networks],
                    a.overrides.model_dump(),
                )
                for a in t.assets
            ],
            t.routing.gateway if t.routing else None,
            (
                (m.instrumentation.mirror_to, tuple(m.instrumentation.exclude))
                if m.instrumentation
                else None
            ),
            (
                [(p.name, p.output_index) for p in m.structuring.protocols]
                if m.structuring
                else None
            ),
        )

    assert snapshot(reloaded) == snapshot(original)


def test_exported_yaml_provisions(harness_path, gui_dir, repo_root, presets, tmp_path):
    """GUIが書き出したYAMLから、実際にdocker-compose.ymlが生成できること。"""
    from generators.compose import generate_compose
    from schema import load_manifest

    original = load_manifest(repo_root / "manifests" / "power-grid-reference.yaml")
    js = run_js_validate(harness_path, gui_dir, manifest_to_model(original))

    exported = tmp_path / "exported.generated.yaml"
    exported.write_text(js["yaml"], encoding="utf-8")

    compose = generate_compose(load_manifest(exported), presets)
    assert compose["services"], "サービスが生成されていない"
    assert "wan_router" in compose["services"]

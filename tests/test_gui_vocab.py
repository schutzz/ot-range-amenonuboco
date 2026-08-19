"""GUI向け生成物(gui/vocab.js・gui/samples.js)の回帰テスト。

GUIはクライアントサイド完結のため、Pythonのモデルをそのまま呼べない
(Phase8決定事項#117)。語彙をJS側へ手書きすると必ずズレるため機械生成に
しているが、「生成を忘れたまま語彙を足した」状態は生成方式そのものでは
防げない。ここで「コミット済みの生成物」と「今のスキーマから生成した結果」
の一致を表明し、再生成忘れをCIで落とす(決定事項#118の封じ込め策①)。

例えば新しいAssetRoleを追加してroles.yamlにプリセットを書いても、
gen_gui_vocab.py を再実行しなければGUIのロール選択肢には現れない。
その状態のままコミットされることを、このテストが防ぐ。
"""

from __future__ import annotations

import json

import pytest

from tools.gen_gui_vocab import build_samples, build_vocab, generate


def test_generated_files_are_up_to_date():
    """gui/*.js が現行スキーマからの生成結果と一致すること。

    落ちた場合は `python platform/tools/gen_gui_vocab.py` を実行して
    生成物を更新する。
    """
    stale = []
    for path, expected in generate().items():
        assert path.is_file(), f"生成物が存在しない: {path}"
        if path.read_text(encoding="utf-8") != expected:
            stale.append(path.name)

    assert not stale, (
        f"生成物が古い: {stale}. "
        "`python platform/tools/gen_gui_vocab.py` を実行して更新すること"
    )


def test_vocab_covers_every_role_and_kind():
    """スキーマのLiteralに列挙された全ロール・全セグメント種別が語彙に載ること。"""
    from typing import get_args

    from schema.topology import AssetRole, SegmentKind

    vocab = build_vocab()

    assert set(vocab["roles"]) == set(get_args(AssetRole))
    assert set(vocab["segmentKinds"]) == set(get_args(SegmentKind))


def test_every_role_has_a_color():
    """全ロールに配色が割り当たっていること(未定義ロールのグレー落ちを防ぐ)。"""
    vocab = build_vocab()
    uncolored = [
        role for role, spec in vocab["roles"].items() if spec["color"] == "#888888"
    ]
    assert not uncolored, (
        f"配色が未定義のロール: {uncolored}. "
        "renderers/network_diagram.py の _ROLE_COLORS に追加すること"
    )


def test_samples_cover_every_manifest():
    """manifests/ の全マニフェストがGUIテンプレートとして同梱されていること。

    分野を1枚足したのに `_SAMPLE_MANIFESTS` への追記を忘れると、
    その分野だけGUIから触れない——ファイルは増えたのにGUIには出てこない、
    という気づきにくい取りこぼしになる。両者を突き合わせて塞ぐ。
    """
    from pathlib import Path

    manifest_dir = Path(__file__).resolve().parent.parent / "manifests"
    on_disk = {
        p.stem
        for p in manifest_dir.glob("*.yaml")
        if not p.name.endswith(".docker-compose.yml") and ".generated." not in p.name
    }
    bundled = {s["id"] for s in build_samples()}
    assert bundled == on_disk, (
        f"GUIに同梱されていない分野: {sorted(on_disk - bundled)} / "
        f"実体の無い同梱: {sorted(bundled - on_disk)}. "
        "platform/tools/gen_gui_vocab.py の _SAMPLE_MANIFESTS を更新すること"
    )


def test_samples_are_grouped_by_depth():
    """各テンプレートが深さの群を持ち、群が既知の3種であること。

    15分野を平坦に並べると、攻撃・検知まで作り込んだ分野と器だけの分野の
    区別が選択肢の上で消える。群の宣言自体を表明として固定する。
    """
    known = {"実演あり", "器のみ", "器のみ・観測境界あり"}
    for sample in build_samples():
        assert sample.get("group") in known, (
            f"{sample['id']}: 未知の群 '{sample.get('group')}'"
        )


@pytest.mark.parametrize("index", range(len(build_samples())))
def test_sample_models_are_json_serializable_and_shaped(index):
    """同梱モデルがJSONとして表現でき、GUIが編集する3層の形を持つこと。"""
    sample = build_samples()[index]
    model = sample["model"]

    json.dumps(model)  # 非シリアライズ可能な値が混ざっていないこと

    assert model["kind"] == "CyberRange"
    assert model["topology"]["segments"], "セグメントが空"
    assert model["topology"]["assets"], "資産が空"
    # 編集対象外の3層(detection/attack/visualization)は落とすこと(決定事項#119)
    assert "detection" not in model
    assert "attack" not in model
    assert "visualization" not in model


def test_sample_models_round_trip_through_pydantic():
    """同梱モデルが、そのままPydanticの検証を通る有効なマニフェストであること。

    GUIはこのモデルを出発点に編集させるため、出発点自体が無効だと
    「読み込んだ直後にエラーが出ている」状態になる。3層に絞っても
    有効なマニフェストが成立する(決定事項#119の前提)ことの確認でもある。
    """
    from schema.topology import Manifest

    for sample in build_samples():
        Manifest.model_validate(sample["model"])

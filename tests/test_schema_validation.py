"""マニフェストのスキーマ・相互参照バリデーションの回帰テスト。

Phase5後の地盤固め(決定事項#75・#76)で塞いだバリデーションの穴を、
「宣言時に弾けること」を保証する回帰テストとして固定する。これらは
いずれも「宣言としては通るが docker compose up で初めて壊れる/静かに
動かない」類の穴であり、実機検証では見つけづらいため自動テスト化の
価値が高い(Phase3〜5でHTTPの密トラフィックでしか検証せず潜在バグを
見逃した罠#018の反省)。
"""

from __future__ import annotations

import copy

import pytest
import yaml
from pydantic import ValidationError

from schema.topology import Manifest


@pytest.fixture
def base_raw(reference_manifest_path):
    return yaml.safe_load(reference_manifest_path.read_text(encoding="utf-8"))


def _validate(raw: dict) -> None:
    Manifest.model_validate(raw)


def test_reference_manifest_is_valid(base_raw):
    """現行のリファレンスマニフェストは妥当であること(基準)。"""
    _validate(base_raw)


# --- ここから: 弾けるべき異常系(REJECT) --------------------------------------


def test_reject_undefined_segment_reference(base_raw):
    base_raw["topology"]["assets"][1]["networks"].append({"segment": "nonexistent"})
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_duplicate_segment_name(base_raw):
    base_raw["topology"]["segments"].append(
        {"name": "cc_lan", "cidr": "10.9.0.0/24", "kind": "it-core"}
    )
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_duplicate_asset_name(base_raw):
    base_raw["topology"]["assets"].append(copy.deepcopy(base_raw["topology"]["assets"][1]))
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_invalid_cidr(base_raw):
    base_raw["topology"]["segments"][0]["cidr"] = "not-a-cidr"
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_gateway_not_l3_router(base_raw):
    base_raw["topology"]["routing"]["gateway"] = "cc_scada_master"
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_gateway_nonexistent_asset(base_raw):
    base_raw["topology"]["routing"]["gateway"] = "nonexistent"
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_unknown_role(base_raw):
    base_raw["topology"]["assets"][1]["role"] = "unknown-role"
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_unknown_segment_kind(base_raw):
    base_raw["topology"]["segments"][0]["kind"] = "unknown-kind"
    with pytest.raises(ValidationError):
        _validate(base_raw)


# --- 地盤固めで新たに塞いだ4件(決定事項#75・#76) ---------------------------


def test_reject_duplicate_ip_in_same_segment(base_raw):
    """同一セグメント内のIP重複(決定事項#75、罠#004と同種)。"""
    # cc_scada_master が 10.1.10.10。別のcc_lan資産に同じIPを付ける。
    base_raw["topology"]["assets"][5]["networks"][0]["ip"] = "10.1.10.10"
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_ip_outside_segment_cidr(base_raw):
    """宣言IPがそのセグメントのCIDR範囲外(決定事項#75)。"""
    base_raw["topology"]["assets"][1]["networks"][0]["ip"] = "192.168.99.99"
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_asset_connects_same_segment_twice(base_raw):
    """同一資産が同じセグメントに二重接続(決定事項#75)。"""
    base_raw["topology"]["assets"][1]["networks"].append(
        {"segment": "cc_lan", "ip": "10.1.10.99"}
    )
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_structuring_without_instrumentation(base_raw):
    """structuring層はinstrumentation層を前提とする(決定事項#76)。"""
    del base_raw["instrumentation"]
    with pytest.raises(ValidationError):
        _validate(base_raw)


# --- 各層の相互参照(Phase2〜4) ----------------------------------------------


def test_reject_mirror_to_nonexistent_segment(base_raw):
    base_raw["instrumentation"]["mirror_to"] = "nonexistent"
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_duplicate_protocol_name(base_raw):
    base_raw["structuring"]["protocols"].append({"name": "http", "output_index": "x-*"})
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_plugin_host_nonexistent(base_raw):
    base_raw["detection"]["plugins"][0]["host"] = "nonexistent"
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_unimplemented_plugin_type(base_raw):
    """Phase4は sidecar のみ実装(決定事項#55)。vector-transform は弾く。"""
    base_raw["detection"]["plugins"][0]["type"] = "vector-transform"
    with pytest.raises(ValidationError):
        _validate(base_raw)


def test_reject_caldera_host_not_attack_engine(base_raw):
    base_raw["attack"]["engine"]["caldera"]["host"] = "cc_scada_master"
    with pytest.raises(ValidationError):
        _validate(base_raw)


# --- 正常系のバリエーション(PASS) -------------------------------------------


def test_accept_dynamic_ip_assets(base_raw):
    """ip省略(動的割当)の資産が、IP整合チェックで誤って弾かれないこと。"""
    # es_enrich_refresher / tap_observer は ip 省略。現行マニフェストで通ること。
    _validate(base_raw)


def test_accept_manifest_without_optional_layers(base_raw):
    """トポロジ層以外は任意。全部外しても通ること(層の任意性)。"""
    for layer in ("instrumentation", "structuring", "detection", "attack"):
        base_raw.pop(layer, None)
    _validate(base_raw)

"""シナリオ資産(scenarios/)とバルクローダーのユニットテスト。

外部サービス(Elasticsearch)に依存しない純粋ロジックだけを対象にする。
前身`ot-ids-verum`から移植したCRC実装や、bulk_loaderのindex名解決など、
「移植・書き直しで壊れやすいが実機を立てずに検証できる」部分を固める。
"""

from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCENARIOS = _REPO_ROOT / "scenarios" / "legacy-power-grid-signals"
_BULK_LOADER = _REPO_ROOT / "platform" / "generators" / "assets" / "bulk_loader.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def dnp3_attack():
    return _load_module("dnp3_zone_attack", _SCENARIOS / "dnp3_zone_attack.py")


@pytest.fixture(scope="module")
def bulk_loader():
    return _load_module("bulk_loader", _BULK_LOADER)


# --- DNP3フレーム生成(前身 Phase-ex/dnp3_frame.py からの移植) ---------------


def test_crc_dnp_known_vector(dnp3_attack):
    """前身が単体テストに使っていた既知ベクタでCRC実装の同一性を確認。"""
    known = dnp3_attack.crc_dnp(bytes([0x05, 0x64, 0x05, 0xC0, 0x01, 0x00, 0x00, 0x00]))
    assert known == bytes([0x91, 0xF8])


def test_dnp3_frame_structure(dnp3_attack):
    """fc=1(READ)の最小フレームが、前身と同じ15バイト・開始バイトを持つこと。"""
    frame = dnp3_attack.build_dnp3_frame(1)
    assert len(frame) == 15
    assert frame[0:2] == b"\x05\x64"


# --- bulk_loader の index名解決(決定事項#49、罠#012) ------------------------


def test_resolve_concrete_index_replaces_wildcard(bulk_loader):
    """ワイルドカードパターンが日次の具体的index名へ解決されること。"""
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y.%m.%d")
    assert bulk_loader._resolve_concrete_index("ot-logs-http-*") == f"ot-logs-http-{today}"


def test_resolve_concrete_index_without_wildcard(bulk_loader):
    """`*`が無いパターンでも日付が付与されること。"""
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y.%m.%d")
    assert bulk_loader._resolve_concrete_index("ot-logs-dnp3") == f"ot-logs-dnp3-{today}"

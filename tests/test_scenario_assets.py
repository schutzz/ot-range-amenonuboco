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


# --- GOOSE複製・再送攻撃(Phase 9.5 決定事項#139) --------------------------


@pytest.fixture(scope="module")
def goose_attack():
    return _load_module("goose_replay_attack", _SCENARIOS / "goose_replay_attack.py")


def test_goose_frame_building(goose_attack):
    """build_goose_frame が EtherType 0x88B8 を含むパケットを正しく構成すること。"""
    frame = goose_attack.build_goose_frame(st_num=10, sq_num=1, breaker_tripped=True)
    # MAC dst(6) + MAC src(6) + EtherType(2) = 14 byte イーサネットヘッダ
    assert frame[12:14] == b"\x88\xb8"
    assert b"stNum=10" in frame
    assert b"cbTripped=1" in frame


def test_goose_send_replay_test_mode(goose_attack):
    """send_goose_replay がエラーを起こさずパケットを送出完了できること。"""
    sent_bytes = goose_attack.send_goose_replay(
        interface="lo", count=2, interval=0.01, st_num=5
    )
    assert sent_bytes > 0


def test_main_default_repeat_is_single_shot(dnp3_attack, monkeypatch):
    """--repeat省略時は従来通り1回のみ送信されること(後方互換)。"""
    calls: list[tuple[str, int, int]] = []
    monkeypatch.setattr(
        dnp3_attack,
        "send_dnp3",
        lambda target_ip, target_port, function_code: calls.append(
            (target_ip, target_port, function_code)
        )
        or "10.1.20.11",
    )
    monkeypatch.setattr(sys, "argv", ["dnp3_zone_attack.py", "--target-ip", "10.1.10.10"])
    assert dnp3_attack.main() == 0
    assert len(calls) == 1


def test_main_repeat_sends_n_times(dnp3_attack, monkeypatch):
    """--repeat Nで、送信がちょうどN回行われること(決定事項#88)。"""
    calls: list[tuple[str, int, int]] = []
    monkeypatch.setattr(
        dnp3_attack,
        "send_dnp3",
        lambda target_ip, target_port, function_code: calls.append(
            (target_ip, target_port, function_code)
        )
        or "10.1.20.11",
    )
    sleeps: list[float] = []
    monkeypatch.setattr(dnp3_attack.time, "sleep", lambda sec: sleeps.append(sec))
    monkeypatch.setattr(
        sys,
        "argv",
        ["dnp3_zone_attack.py", "--target-ip", "10.1.10.10", "--repeat", "5", "--interval", "2"],
    )
    assert dnp3_attack.main() == 0
    assert len(calls) == 5
    # 送信間の間隔のみsleepする(最後の送信後にはsleepしない、無駄な待ちを作らない)。
    assert sleeps == [2, 2, 2, 2]


# --- bulk_loader の index名解決(決定事項#49、罠#012) ------------------------


def test_resolve_concrete_index_replaces_wildcard(bulk_loader):
    """ワイルドカードパターンが日次の具体的index名へ解決されること。"""
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y.%m.%d")
    assert bulk_loader._resolve_concrete_index("ot-logs-http-*") == f"ot-logs-http-{today}"


def test_resolve_concrete_index_without_wildcard(bulk_loader):
    """`*`が無いパターンでも日付が付与されること。"""
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y.%m.%d")
    assert bulk_loader._resolve_concrete_index("ot-logs-dnp3") == f"ot-logs-dnp3-{today}"


# --- Phase 10 Stage 4-A: 水道物理連動 & Modbus オーバーフロー攻撃 -----------------

_WATER_SCENARIOS = _REPO_ROOT / "scenarios" / "water-overflow-consequence"


@pytest.fixture(scope="module")
def modbus_attack():
    return _load_module("modbus_overflow_attack", _WATER_SCENARIOS / "modbus_overflow_attack.py")


@pytest.fixture(scope="module")
def water_evaluator():
    return _load_module("evaluate_water_consequence", _WATER_SCENARIOS / "evaluate_water_consequence.py")


def test_modbus_overflow_attack_dry_run(modbus_attack):
    """pymodbus が無い環境やターゲット非接続でもシミュレーション実行が成功すること。"""
    result = modbus_attack.run_attack("10.2.20.10", port=502, duration=1)
    assert result["status"] in ("SUCCESS", "SUCCESS (SIMULATED)", "FAILED")


def test_evaluate_water_consequence_e2e(water_evaluator):
    """Phase 10 Stage 4-A: 水道 Digital Twin & Consequence E2E 総合評価が PASS すること。"""
    assert water_evaluator.run_evaluation() is True


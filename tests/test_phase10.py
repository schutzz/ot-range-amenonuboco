"""Phase 10 Stage 1 / Stage 2 / Stage 3 テスト:
  - ImpairmentSpec スキーマバリデーション（#144/#153/#154）
  - PhysicalProcessSpec バリデーション（observed_by 必須 / 別セグメント強制 / #152）
  - generate_impairment_commands_with_cidr の tc コマンド生成
  - TankLevelModel の物理計算ロジック
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from schema.topology import Manifest

# ---------------------------------------------------------------------------
# テスト用マニフェスト dict 組立ヘルパー
# ---------------------------------------------------------------------------
MINIMAL_MANIFEST_DICT = {
    "apiVersion": "amenonuboco/v1",
    "kind": "CyberRange",
    "metadata": {"name": "test-impairment"},
    "topology": {
        "segments": [
            {"name": "cc_lan",      "cidr": "10.1.10.0/24", "kind": "ot-lan"},
            {"name": "sub_a_lan",   "cidr": "10.1.20.0/24", "kind": "ot-l2"},
            {"name": "mirror_link", "cidr": "10.99.0.0/24", "kind": "observation"},
        ],
        "assets": [
            {
                "name": "gateway",
                "role": "l3-router",
                "image": "frrouting/frr:latest",
                "networks": [
                    {"segment": "cc_lan",      "ip": "10.1.10.1"},
                    {"segment": "sub_a_lan",   "ip": "10.1.20.1"},
                    {"segment": "mirror_link", "ip": "10.99.0.1"},
                ],
            },
            {
                "name": "water_plc",
                "role": "ot-asset",
                "image": "../protocol-images/modbus",
                "networks": [{"segment": "sub_a_lan", "ip": "10.1.20.10"}],
            },
            {
                "name": "scada_hmi",
                "role": "ot-asset",
                "image": "../protocol-images/modbus",
                "networks": [{"segment": "cc_lan", "ip": "10.1.10.20"}],
            },
            {
                "name": "tap_observer",
                "role": "observer",
                "image": "ghcr.io/amenonuboco/tap-observer:latest",
                "networks": [{"segment": "mirror_link", "ip": "10.99.0.10"}],
            },
        ],
        "routing": {"gateway": "gateway"},
    },
    "instrumentation": {
        "engine": "linux-tc",
        "mirror_to": "mirror_link",
    },
}


def _m(**kwargs) -> dict:
    """テスト用マニフェスト dict を組み立てるヘルパー。"""
    d = copy.deepcopy(MINIMAL_MANIFEST_DICT)

    if kwargs.get("impair_seg"):
        for s in d["topology"]["segments"]:
            if s["name"] == kwargs["impair_seg"]:
                s["impairment"] = {"delay": "100ms", "jitter": "20ms", "loss": "1.5%"}

    if kwargs.get("impair_mirror"):
        for s in d["topology"]["segments"]:
            if s["name"] == "mirror_link":
                s["impairment"] = {"delay": "50ms"}

    if kwargs.get("impair_rate"):
        for s in d["topology"]["segments"]:
            if s["name"] == "sub_a_lan":
                s["impairment"] = {"delay": "50ms", "rate": "9600bit"}

    if kwargs.get("remove_instrumentation"):
        del d["instrumentation"]

    if kwargs.get("partial_impair"):
        for s in d["topology"]["segments"]:
            if s["name"] == "sub_a_lan":
                s["impairment"] = {"delay": "200ms"}

    if kwargs.get("physical_process"):
        obs_name = kwargs.get("observer_name", "scada_hmi")
        obs_same_seg = kwargs.get("observer_same_seg", False)
        obs_seg = "sub_a_lan" if obs_same_seg else "cc_lan"
        obs_ip  = "10.1.20.30" if obs_same_seg else "10.1.10.20"
        for a in d["topology"]["assets"]:
            if a["name"] == "scada_hmi":
                a["networks"] = [{"segment": obs_seg, "ip": obs_ip}]
        for a in d["topology"]["assets"]:
            if a["name"] == "water_plc":
                a["physical_process"] = {
                    "type": "tank_level",
                    "initial_level": 50.0,
                    "capacity": 100.0,
                    "update_interval": "0.5s",
                    "bind_registers": {"level_sensor": 40001, "pump_control": 40002},
                    "observed_by": obs_name,
                }

    if kwargs.get("nonexistent_observer"):
        for a in d["topology"]["assets"]:
            if a["name"] == "water_plc":
                a["physical_process"] = {
                    "type": "tank_level",
                    "bind_registers": {},
                    "observed_by": "nonexistent_asset",
                }

    if kwargs.get("no_bind_registers"):
        for a in d["topology"]["assets"]:
            if a["name"] == "water_plc":
                a["physical_process"] = {
                    "type": "temperature",
                    "observed_by": "scada_hmi",
                }

    return d


def _validate(d: dict) -> Manifest:
    return Manifest.model_validate(d)


# ===========================================================================
# Stage 1: ImpairmentSpec バリデーション
# ===========================================================================

class TestImpairmentSpec:
    """#144 / #153 / #154 のスキーマバリデーションテスト。"""

    def test_impairment_on_normal_segment_is_accepted(self):
        """通常セグメント（mirror_to 以外）への impairment 宣言は受理される。"""
        manifest = _validate(_m(impair_seg="sub_a_lan"))
        seg = manifest.topology.segment_by_name("sub_a_lan")
        assert seg.impairment is not None
        assert seg.impairment.delay == "100ms"
        assert seg.impairment.jitter == "20ms"
        assert seg.impairment.loss == "1.5%"

    def test_impairment_on_mirror_segment_is_rejected(self):
        """mirror_to セグメントへの impairment 宣言は生成時エラーになる（#154）。"""
        with pytest.raises((ValidationError, Exception)):
            _validate(_m(impair_mirror=True))

    def test_impairment_without_instrumentation_is_accepted(self):
        """instrumentation 未宣言の場合、mirror_to が無いため impairment は受理。"""
        manifest = _validate(_m(impair_seg="sub_a_lan", remove_instrumentation=True))
        seg = manifest.topology.segment_by_name("sub_a_lan")
        assert seg.impairment is not None

    def test_impairment_partial_spec_is_accepted(self):
        """delay のみの部分仕様も受理される。"""
        manifest = _validate(_m(partial_impair=True))
        seg = manifest.topology.segment_by_name("sub_a_lan")
        assert seg.impairment.delay == "200ms"
        assert seg.impairment.jitter is None
        assert seg.impairment.loss is None
        assert seg.impairment.rate is None

    def test_segment_without_impairment_has_none(self):
        """impairment 未宣言のセグメントの impairment フィールドは None。"""
        manifest = _validate(_m())
        seg = manifest.topology.segment_by_name("sub_a_lan")
        assert seg.impairment is None


# ===========================================================================
# Stage 1: PhysicalProcessSpec バリデーション
# ===========================================================================

class TestPhysicalProcessSpec:
    """#146 / #152 の physical_process バリデーションテスト。"""

    def test_physical_process_with_valid_observed_by_is_accepted(self):
        """valid: observed_by が別セグメントの実在資産を指す場合は受理。"""
        manifest = _validate(_m(physical_process=True))
        plc = manifest.topology.asset_by_name("water_plc")
        assert plc.physical_process is not None
        assert plc.physical_process.observed_by == "scada_hmi"
        assert plc.physical_process.type == "tank_level"

    def test_physical_process_nonexistent_observer_is_rejected(self):
        """invalid: observed_by が存在しない資産名を指す場合はエラー。"""
        with pytest.raises((ValidationError, Exception)):
            _validate(_m(nonexistent_observer=True))

    def test_physical_process_same_segment_observer_is_rejected(self):
        """invalid: observed_by が同一セグメント資産を指す場合はエラー（#152）。"""
        with pytest.raises((ValidationError, Exception)):
            _validate(_m(physical_process=True, observer_same_seg=True))

    def test_physical_process_bind_registers_defaults(self):
        """bind_registers 省略時はデフォルト空 dict で受理される。"""
        manifest = _validate(_m(no_bind_registers=True))
        plc = manifest.topology.asset_by_name("water_plc")
        assert plc.physical_process.bind_registers == {}

    def test_asset_without_physical_process_has_none(self):
        """physical_process 未宣言の資産の physical_process は None。"""
        manifest = _validate(_m())
        plc = manifest.topology.asset_by_name("water_plc")
        assert plc.physical_process is None


# ===========================================================================
# Stage 2: tc-netem コマンド生成テスト
# ===========================================================================

class TestImpairmentCommandGeneration:
    """generate_impairment_commands_with_cidr のユニットテスト。"""

    def _gen(self, d: dict):
        from generators.impairment import generate_impairment_commands_with_cidr
        return generate_impairment_commands_with_cidr(_validate(d))

    def test_no_impairment_segments_returns_empty(self):
        """impairment 宣言が一切無ければ空 dict を返す。"""
        assert self._gen(_m()) == {}

    def test_impairment_segment_generates_tc_commands(self):
        """impairment 宣言があるセグメントの tc コマンドが生成される。"""
        result = self._gen(_m(impair_seg="sub_a_lan"))
        assert "sub_a_lan" in result
        cmds = result["sub_a_lan"]
        # GW_IF 解決コマンドが含まれる
        assert any("GW_IF" in c for c in cmds)
        # netem アタッチコマンドに delay と loss が含まれる
        netem_cmd = next(c for c in cmds if "netem" in c and "add" in c)
        assert "delay 100ms 20ms" in netem_cmd
        assert "loss 1.5%" in netem_cmd

    def test_rate_generates_tbf_child(self):
        """rate 指定時は netem の子として TBF qdisc が追加される。"""
        result = self._gen(_m(impair_rate=True))
        cmds = result["sub_a_lan"]
        tbf_cmd = next((c for c in cmds if "tbf" in c), None)
        assert tbf_cmd is not None, "rate 指定時は TBF コマンドが生成されるべき"
        assert "9600bit" in tbf_cmd

    def test_no_impairment_segments_are_excluded(self):
        """impairment が無いセグメントは生成結果に含まれない。"""
        result = self._gen(_m(impair_seg="sub_a_lan"))
        assert "cc_lan" not in result
        assert "mirror_link" not in result

    def test_cidr_prefix_replaces_seg_name_in_commands(self):
        """生成コマンドには CIDR prefix が含まれる（sub_a_lan の CIDR は 10.1.20.0/24）。"""
        result = self._gen(_m(impair_seg="sub_a_lan"))
        cmds = result["sub_a_lan"]
        # CIDR は 10.1.20.0/24 → prefix は "10.1.20"
        assert any("10.1.20" in c for c in cmds), (
            f"CIDR prefix (10.1.20) がコマンドに含まれるべき: {cmds}"
        )


# ===========================================================================
# Stage 3: Physical Engine (tank_level) のユニットテスト
# ===========================================================================

def _load_tank_level_mod():
    """scenarios/physical_models/tank_level.py を動的ロードするヘルパー。"""
    tank_path = (
        Path(__file__).parent.parent
        / "scenarios" / "physical_models" / "tank_level.py"
    )
    spec = importlib.util.spec_from_file_location("tank_level", tank_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTankLevelModel:
    """TankLevelModel の物理計算ロジックのユニットテスト。"""

    @pytest.fixture(autouse=True)
    def _mod(self):
        self.mod = _load_tank_level_mod()

    def _make(self, **kwargs):
        return self.mod.TankLevelModel(client=None, **kwargs)

    def test_initial_level_is_set(self):
        model = self._make(initial_level=30.0)
        assert model.level == 30.0

    def test_pump_on_increases_level(self):
        """ポンプ ON 時は水位が上昇する。"""
        model = self._make(initial_level=50.0, q_in=5.0, q_out=2.0, dt=1.0)
        new_level = model.step(pump_on=True)
        assert new_level == pytest.approx(53.0)  # 50 + (5-2)*1

    def test_pump_off_decreases_level(self):
        """ポンプ OFF 時は自然流出で水位が低下する。"""
        model = self._make(initial_level=50.0, q_in=5.0, q_out=2.0, dt=1.0)
        new_level = model.step(pump_on=False)
        assert new_level == pytest.approx(48.0)  # 50 + (0-2)*1

    def test_overflow_clamped_to_capacity(self):
        """水位が capacity を超えたらクランプされる。"""
        model = self._make(initial_level=99.0, q_in=5.0, q_out=0.0, dt=1.0)
        new_level = model.step(pump_on=True)
        assert new_level == pytest.approx(100.0)

    def test_underflow_clamped_to_zero(self):
        """水位が 0 を下回ったらクランプされる。"""
        model = self._make(initial_level=1.0, q_in=0.0, q_out=5.0, dt=1.0)
        new_level = model.step(pump_on=False)
        assert new_level == pytest.approx(0.0)

    def test_multiple_steps_accumulate(self):
        """複数ステップの累積計算が正しい。"""
        model = self._make(initial_level=0.0, q_in=10.0, q_out=0.0, dt=0.1)
        for _ in range(10):
            model.step(pump_on=True)
        assert model.level == pytest.approx(10.0, abs=0.01)

    def test_dry_run_read_pump_returns_false(self):
        """DRY_RUN モード（client=None）の read_pump_state は False。"""
        model = self._make()
        assert model.read_pump_state() is False

    def test_dry_run_write_level_is_noop(self):
        """DRY_RUN モード（client=None）の write_level は例外を出さない。"""
        model = self._make()
        model.write_level(500)  # 例外なく通過することを確認

    def test_run_loop_bounded(self):
        """max_steps 指定時は指定回数で終了する（無限ループしない）。"""
        model = self._make(initial_level=50.0, dt=0.0)
        model.run_loop(max_steps=5)
        assert model.level == pytest.approx(50.0)

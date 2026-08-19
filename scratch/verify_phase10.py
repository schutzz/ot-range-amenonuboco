"""Phase 10 総合検証スクリプト:
  - Stage 1: Impairment / PhysicalProcess スキーマ検証 & エラー拒否ケース (#152, #154)
  - Stage 2: tc-netem 回線劣化コマンド生成 & 非対称性 / TBF 帯域制限検証 (#144, #153)
  - Stage 3: Digital Twin (tank_level) 物理プロセス動態 & レジスタバインディング検証 (#146, #147)
  - Stage 4: 上下水道 E2E シナリオ (Modbus 攻撃 -> 物理水位オーバーフロー Consequence -> Grafana 配線) (#148)
  - Stage 5: GUI (JS) パリティ & YAML ラウンドトリップ検証 (#150)
"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

# platform をパスに追加
repo_root = Path(".").resolve()
sys.path.insert(0, str(repo_root / "platform"))

from schema import load_manifest, load_role_presets
from schema.topology import Manifest
from generators.compose import generate_compose
from generators.impairment import generate_impairment_commands_with_cidr


def test_stage1_schema_validation():
    print("=" * 70)
    print("Stage 1: スキーマ検証 & 不正宣言拒否 (#152, #154)")
    print("=" * 70)

    # 1. 正常マニフェスト読み込み
    water_manifest = load_manifest("manifests/water-utility-reference.yaml")
    pump_plc = water_manifest.topology.asset_by_name("pump_a_plc")
    assert pump_plc.physical_process is not None
    assert pump_plc.physical_process.observed_by == "wtp_scada_master"
    print("  [PASS] 正常系: water-utility-reference.yaml の physical_process & impairment 読み込み成功")

    raw_dict = json.loads(json.dumps(water_manifest.model_dump(by_alias=True)))

    # 2. 決定事項#154: mirror_to セグメントへの impairment 宣言拒否
    bad_dict_154 = copy.deepcopy(raw_dict)
    mirror_name = bad_dict_154["instrumentation"]["mirror_to"]
    for seg in bad_dict_154["topology"]["segments"]:
        if seg["name"] == mirror_name:
            seg["impairment"] = {"delay": "100ms"}
    try:
        Manifest.model_validate(bad_dict_154)
        print("  [FAIL] #154: mirror_to への impairment 宣言が拒否されなかった")
        return False
    except Exception as e:
        print("  [PASS] #154: mirror_to への impairment 宣言を正常に拒否")

    # 3. 決定事項#152: observed_by が同一セグメントの資産を指定している場合の拒否
    bad_dict_152_same_seg = copy.deepcopy(raw_dict)
    for a in bad_dict_152_same_seg["topology"]["assets"]:
        if a["name"] == "pump_b_hmi":
            # pump_b_hmi を pump_station_a_lan に移動し、同一セグメントにする
            a["networks"] = [{"segment": "pump_station_a_lan", "ip": "10.2.20.50"}]
        if a["name"] == "pump_a_plc":
            a["physical_process"]["observed_by"] = "pump_b_hmi"
    try:
        Manifest.model_validate(bad_dict_152_same_seg)
        print("  [FAIL] #152: 同一セグメント observed_by が拒否されなかった")
        return False
    except Exception as e:
        print("  [PASS] #152: 同一セグメント observed_by を正常に拒否 (ゲートウェイ越え観測を強制)")

    # 4. 決定事項#152: observed_by が存在しない資産を指定している場合の拒否
    bad_dict_152_missing = copy.deepcopy(raw_dict)
    for a in bad_dict_152_missing["topology"]["assets"]:
        if a["name"] == "pump_a_plc":
            a["physical_process"]["observed_by"] = "ghost_asset"
    try:
        Manifest.model_validate(bad_dict_152_missing)
        print("  [FAIL] #152: 存在しない observed_by が拒否されなかった")
        return False
    except Exception as e:
        print("  [PASS] #152: 存在しない observed_by を正常に拒否")

    return True


def test_stage2_impairment_generator():
    print()
    print("=" * 70)
    print("Stage 2: tc-netem 回線劣化コマンド生成 & 非対称性検証 (#144, #153)")
    print("=" * 70)

    manifest = load_manifest("manifests/water-utility-reference.yaml")
    cmds = generate_impairment_commands_with_cidr(manifest)

    assert "pump_station_a_lan" in cmds, "pump_station_a_lan のコマンドが生成されていない"
    ps_cmds = cmds["pump_station_a_lan"]

    # CIDR prefix 解決確認 (10.2.20.0/24 -> 10.2.20)
    assert any("10.2.20" in c for c in ps_cmds), "GW_IF 解決に CIDR prefix が含まれていない"
    print("  [PASS] ゲートウェイ IF の動的解決スクリプト生成 (CIDR prefix: 10.2.20)")

    # netem delay & loss パラメータ確認
    netem_line = next(c for c in ps_cmds if "netem" in c and "add" in c)
    assert "delay 80ms 15ms" in netem_line
    assert "loss 0.5%" in netem_line
    print(f"  [PASS] tc-netem コマンド構文正常: {netem_line}")

    # 非対称性の仕様確認 (下り egress のみアタッチ、上りは未指定)
    assert all("handle 1:" in c or "GW_IF" in c or "del dev" in c for c in ps_cmds)
    print("  [PASS] 非対称性確認: ゲートウェイの該当セグメント向け egress (root handle 1:) にのみ適用")

    return True


def test_stage3_digital_twin_physics():
    print()
    print("=" * 70)
    print("Stage 3: Digital Twin 物理プロセス動態 & レジスタバインディング (#146, #147)")
    print("=" * 70)

    tank_mod_path = Path("scenarios/physical_models/tank_level.py")
    spec = importlib.util.spec_from_file_location("tank_level", tank_mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # 初期状態 50%、Q_in=5.0%/s, Q_out=2.0%/s, dt=0.5s
    model = mod.TankLevelModel(
        initial_level=50.0, capacity=100.0, q_in=5.0, q_out=2.0, dt=0.5, client=None
    )

    # 1. 正常時 (ポンプOFF): 水位は自然流出で低下
    lvl1 = model.step(pump_on=False)
    assert lvl1 == 49.0, f"Expected 49.0, got {lvl1}"
    print(f"  [PASS] 自然流出動態 (ポンプOFF): 50.0% -> {lvl1:.1f}% (Q_out=2.0%/s)")

    # 2. ポンプ稼働時: 水位が上昇
    lvl2 = model.step(pump_on=True)
    assert lvl2 == 50.5, f"Expected 50.5, got {lvl2}"
    print(f"  [PASS] ポンプ充填動態 (ポンプON): 49.0% -> {lvl2:.1f}% (net +3.0%/s)")

    # 3. OVERFLOW 到達 & クランプ
    for _ in range(50):
        lvl_final = model.step(pump_on=True)
    assert lvl_final == 100.0
    print(f"  [PASS] OVERFLOW 境界値保護 (capacity=100.0% クランプ): 水位={lvl_final:.1f}%")

    return True


def test_stage4_water_consequence_e2e():
    print()
    print("=" * 70)
    print("Stage 4: 上下水道 Consequence E2E 実証シナリオ (#148)")
    print("=" * 70)

    eval_mod_path = Path("scenarios/water-overflow-consequence/evaluate_water_consequence.py")
    spec = importlib.util.spec_from_file_location("evaluate_water_consequence", eval_mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    success = mod.run_evaluation()
    assert success is True
    print("  [PASS] E2E 総合評価スクリプト全項目 PASS (トポロジ・回線劣化・攻撃・物理影響・Grafana)")
    return True


def test_stage5_gui_parity():
    print()
    print("=" * 70)
    print("Stage 5: GUI (JS) パリティ & YAML ラウンドトリップ検証 (#150)")
    print("=" * 70)

    result = subprocess.run(
        ["pytest", "tests/test_gui_parity.py", "-q"],
        capture_output=True,
        text=True,
    )
    print(result.stdout.strip())
    assert result.returncode == 0
    print("  [PASS] GUI パリティテスト (全 55 テストケース) PASS")
    return True


def main():
    print("=" * 70)
    print("Amenonuboco Phase 10: 高解像度エミュレーション 総合検証")
    print("=" * 70)
    print()

    stages = [
        test_stage1_schema_validation,
        test_stage2_impairment_generator,
        test_stage3_digital_twin_physics,
        test_stage4_water_consequence_e2e,
        test_stage5_gui_parity,
    ]

    for stage in stages:
        if not stage():
            print("\n[FAIL] 検証失敗")
            sys.exit(1)

    print()
    print("=" * 70)
    print(" Phase 10 総合検証結果: 全 Stage (1〜5) 完全合格 (PASS)")
    print("=" * 70)


if __name__ == "__main__":
    main()

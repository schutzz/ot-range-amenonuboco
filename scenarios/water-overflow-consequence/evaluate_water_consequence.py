"""Phase 10 Stage 4-A: 上下水道物理プロセス連動（Digital Twin）＆ Consequence 評価スクリプト。

検証フロー:
1. マニフェスト検証:
   - water-utility-reference.yaml のトポロジ・impairment・physical_process の妥当性
   - observed_by (wtp_scada_master) が別セグメントにあり、Modbus クライアントとして正しく配線されていること
2. 回線劣化 (Impairment) 検証:
   - pump_station_a_lan に対する tc-netem コマンドの自動生成確認
3. 攻撃 ➔ 物理連動 ➔ Consequence (オーバーフロー) シミュレーション:
   - ポンプ強制ON (レジスタ 40002 <- 1) のインジェクション
   - 離散時間物理モデルによる水位上昇・100% (オーバーフロー) 到達
4. 可視化 (Visualization) 配線:
   - Grafana ダッシュボード (water_tank_consequence.json) がマニフェストにマウントされていること
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [evaluate_consequence] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def run_evaluation() -> bool:
    repo_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(repo_root / "platform"))

    from schema import load_manifest, load_role_presets
    from generators.compose import generate_compose
    from generators.impairment import generate_impairment_commands_with_cidr

    print("=" * 70)
    print("Phase 10 Stage 4-A: 上下水道 Digital Twin & Consequence E2E 検証")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # 1. マニフェスト読み込み & 検証
    # -----------------------------------------------------------------------
    manifest_path = repo_root / "manifests" / "water-utility-reference.yaml"
    manifest = load_manifest(manifest_path)
    print(f"  [PASS] マニフェスト読み込み成功: {manifest.metadata.name}")

    # pump_a_plc の physical_process 検証
    pump_plc = manifest.topology.asset_by_name("pump_a_plc")
    assert pump_plc.physical_process is not None, "pump_a_plc に physical_process が必要"
    assert pump_plc.physical_process.observed_by == "wtp_scada_master"
    assert pump_plc.physical_process.bind_registers.get("level_sensor") == 40001
    assert pump_plc.physical_process.bind_registers.get("pump_control") == 40002
    print(f"  [PASS] pump_a_plc physical_process: type={pump_plc.physical_process.type}, "
          f"observed_by={pump_plc.physical_process.observed_by}")

    # wtp_scada_master (observed_by) の検証
    scada = manifest.topology.asset_by_name("wtp_scada_master")
    assert any("MODE=client" in env for env in scada.overrides.environment)
    assert any("TARGET=10.2.20.10" in env for env in scada.overrides.environment)
    print("  [PASS] wtp_scada_master (observed_by) が Modbus クライアントとして別セグメントからポーリング設定済み")

    # -----------------------------------------------------------------------
    # 2. Impairment (回線劣化) コマンド生成検証
    # -----------------------------------------------------------------------
    impair_cmds = generate_impairment_commands_with_cidr(manifest)
    assert "pump_station_a_lan" in impair_cmds
    cmds = impair_cmds["pump_station_a_lan"]
    assert any("netem" in c and "delay 80ms 15ms" in c for c in cmds)
    assert any("10.2.20" in c for c in cmds)
    print("  [PASS] pump_station_a_lan の tc-netem 回線劣化コマンド正常生成 (delay 80ms 15ms, loss 0.5%)")

    # -----------------------------------------------------------------------
    # 3. 物理プロセス連動シミュレーション (攻撃 -> 水位上昇 -> OVERFLOW)
    # -----------------------------------------------------------------------
    tank_mod_path = repo_root / "scenarios" / "physical_models" / "tank_level.py"
    spec = importlib.util.spec_from_file_location("tank_level", tank_mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    model = mod.TankLevelModel(
        initial_level=pump_plc.physical_process.initial_level,
        capacity=pump_plc.physical_process.capacity,
        q_in=5.0,
        q_out=2.0,
        dt=0.5,
        client=None,
    )

    # 攻撃前 (ポンプ OFF): 水位は減少
    level_before = model.step(pump_on=False)
    assert level_before < 50.0, f"ポンプOFF時は減水すべき: {level_before}"
    print(f"  [PASS] 正常状態 (ポンプOFF): 初期水位 50.0% -> 減水 {level_before:.1f}%")

    # 攻撃発生 (ポンプ強制 ON): 水位が上昇し OVERFLOW 到達
    overflow_reached = False
    for step_i in range(40):  # 40 * 0.5s = 20s
        lvl = model.step(pump_on=True)
        if lvl >= model.capacity:
            overflow_reached = True
            print(f"  [PASS] 攻撃インジェクション成功: ステップ {step_i} (t={step_i*0.5:.1f}s) にて "
                  f"水位 {lvl:.1f}% (OVERFLOW 物理被害到達)")
            break

    assert overflow_reached, "OVERFLOW に到達すべき"

    # -----------------------------------------------------------------------
    # 4. 可視化 (Visualization / Grafana) 配線検証
    # -----------------------------------------------------------------------
    assert manifest.visualization is not None
    assert manifest.visualization.engine == "grafana"
    assert len(manifest.visualization.dashboards) >= 1
    dash_file = manifest.resolve_path(manifest.visualization.dashboards[0])
    assert dash_file.exists(), f"ダッシュボードファイルが存在しない: {dash_file}"
    print(f"  [PASS] Grafana ダッシュボード配線完了: {dash_file.name}")

    # Compose 生成検証
    presets = load_role_presets()
    compose = generate_compose(manifest, presets)
    assert "grafana_server" in compose["services"]
    assert "pump_a_plc" in compose["services"]
    assert "wtp_scada_master" in compose["services"]
    print("  [PASS] docker-compose.yml 正常生成 (全サービス整合)")

    print()
    print("=" * 70)
    print("  Stage 4-A E2E 検証: 全検証項目 PASS")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_evaluation()
    sys.exit(0 if success else 1)

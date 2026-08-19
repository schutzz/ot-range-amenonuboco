"""Digital Twin: タンク水位の離散時間物理モデル（Phase 10 決定事項#147）。

アーキテクチャ:
    PLC コンテナ内で Modbus サーバ（run.py）と並行してバックグラウンドプロセスとして
    起動する。起動コマンドの例:
        ( MODE=server LABEL=water_plc_01 python3 /app/run.py &
          python3 /app/physical/tank_level.py &
          wait )

物理モデル:
    離散時間タンク水位方程式:
        L_{t+1} = L_{t} + (Q_in - Q_out) * dt
    - L   : タンク水位 [%] (0.0 〜 capacity)
    - Q_in: ポンプ吐出量 [%/s]（ポンプ制御レジスタ=1のとき有効）
    - Q_out: 排水流量 [%/s]（常時一定、自然流出を模擬）
    - dt  : 計算ステップ [s]（update_interval で設定）

レジスタバインディング（Modbus Holding Register）:
    - bind_registers.level_sensor (例: 40001): 現在水位を書き込み（出力）
    - bind_registers.pump_control  (例: 40002): ポンプON/OFFフラグを読み取り（入力）

環境変数（マニフェストの overrides.environment に相当）:
    TANK_HOST        : Modbus サーバのホスト (デフォルト: 127.0.0.1)
    TANK_PORT        : Modbus サーバのポート (デフォルト: 502)
    INITIAL_LEVEL    : 初期水位 % (デフォルト: 50.0)
    CAPACITY         : 水位上限 % (デフォルト: 100.0)
    UPDATE_INTERVAL  : 計算周期 秒 (デフォルト: 0.5)
    REGISTER_LEVEL   : 水位センサのレジスタ番号 (デフォルト: 40001)
    REGISTER_PUMP    : ポンプ制御のレジスタ番号 (デフォルト: 40002)
    Q_IN             : ポンプ ON 時の充填速度 %/s (デフォルト: 5.0)
    Q_OUT            : 自然流出速度 %/s (デフォルト: 2.0)
    DRY_RUN          : "1" にすると Modbus 接続なし・標準出力のみ（テスト用）
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

# 環境変数から設定を読み込む
TANK_HOST = os.environ.get("TANK_HOST", "127.0.0.1")
TANK_PORT = int(os.environ.get("TANK_PORT", "502"))
INITIAL_LEVEL = float(os.environ.get("INITIAL_LEVEL", "50.0"))
CAPACITY = float(os.environ.get("CAPACITY", "100.0"))
UPDATE_INTERVAL = float(os.environ.get("UPDATE_INTERVAL", "0.5"))
REGISTER_LEVEL = int(os.environ.get("REGISTER_LEVEL", "40001"))
REGISTER_PUMP = int(os.environ.get("REGISTER_PUMP", "40002"))
Q_IN = float(os.environ.get("Q_IN", "5.0"))    # %/s（ポンプON時の充填速度）
Q_OUT = float(os.environ.get("Q_OUT", "2.0"))  # %/s（自然流出速度）
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"

# Modbus Holding Register のオフセット（アドレス 40001 → register 0）
_HOLD_OFFSET = 40001


def addr_to_reg(addr: int) -> int:
    """Modbus アドレス（4xxxx 形式）をゼロ起点レジスタインデックスに変換。"""
    return addr - _HOLD_OFFSET


class TankLevelModel:
    """タンク水位の離散時間状態方程式モデル。

    テスト容易性のため Modbus クライアントをコンストラクタ注入にする。
    client=None の場合は DRY_RUN モード（標準出力のみ）。
    """

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
        self.client = client  # pymodbus ModbusTcpClient or None

    # ------------------------------------------------------------------
    # Modbus I/O
    # ------------------------------------------------------------------

    def read_pump_state(self) -> bool:
        """ポンプ制御レジスタ（pump_control）を読み取る。ON=True / OFF=False。"""
        if self.client is None:
            return False  # DRY_RUN: 常にOFF
        rr = self.client.read_holding_registers(
            addr_to_reg(REGISTER_PUMP), count=1
        )
        if rr.isError():
            log.warning("pump_control register read failed; assuming OFF")
            return False
        return bool(rr.registers[0])

    def write_level(self, level_int: int) -> None:
        """水位センサレジスタ（level_sensor）に整数値（%×10, 0〜1000）を書き込む。"""
        if self.client is None:
            return  # DRY_RUN: 書き込みスキップ
        self.client.write_register(addr_to_reg(REGISTER_LEVEL), level_int)

    # ------------------------------------------------------------------
    # 物理モデル計算
    # ------------------------------------------------------------------

    def step(self, pump_on: bool) -> float:
        """1タイムステップ分の水位を計算して返す。

        Args:
            pump_on: ポンプが ON かどうか
        Returns:
            更新後の水位 [%]
        """
        effective_q_in = self.q_in if pump_on else 0.0
        delta = (effective_q_in - self.q_out) * self.dt
        self.level = max(0.0, min(self.capacity, self.level + delta))
        return self.level

    # ------------------------------------------------------------------
    # メインループ
    # ------------------------------------------------------------------

    def run_loop(self, max_steps: int = -1) -> None:
        """メインループ。max_steps=-1 の場合は無限ループ（本番用）。

        OVERFLOW しきい値（capacity）を超えた場合は CRITICAL ログを出力する。
        （tshark が構造化して Elasticsearch → Grafana で可視化する対象）
        """
        step_count = 0
        log.info(
            "tank_level engine started: level=%.1f%% capacity=%.1f%% "
            "Q_in=%.2f%%/s Q_out=%.2f%%/s dt=%.2fs",
            self.level, self.capacity, self.q_in, self.q_out, self.dt,
        )

        while max_steps < 0 or step_count < max_steps:
            pump_on = self.read_pump_state()
            new_level = self.step(pump_on)

            # 整数化（%×10）してレジスタへ書き込む（0.1%刻み精度）
            level_int = int(new_level * 10)
            self.write_level(level_int)

            log.info(
                "t=%d pump=%s level=%.1f%% (reg=%d)",
                step_count, "ON" if pump_on else "OFF", new_level, level_int,
            )

            if new_level >= self.capacity:
                log.critical(
                    "OVERFLOW DETECTED: level=%.1f%% >= capacity=%.1f%% "
                    "— physical consequence threshold exceeded!",
                    new_level, self.capacity,
                )

            time.sleep(self.dt)
            step_count += 1


def main() -> None:
    """エントリポイント。PLC コンテナ内でサイドカープロセスとして起動される。"""
    client = None

    if not DRY_RUN:
        try:
            from pymodbus.client import ModbusTcpClient  # type: ignore[import]

            client = ModbusTcpClient(TANK_HOST, port=TANK_PORT)
            connected = client.connect()
            if not connected:
                log.warning(
                    "Modbus connection to %s:%d failed; running in DRY_RUN mode",
                    TANK_HOST, TANK_PORT,
                )
                client = None
        except ImportError:
            log.warning("pymodbus not available; running in DRY_RUN mode")

    model = TankLevelModel(client=client)
    try:
        model.run_loop()
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()

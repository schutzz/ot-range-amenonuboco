"""マニフェストの攻撃層(attack)を表す Pydantic モデル。

Phase0決定事項#2: 攻撃はパッケージ化しない。マニフェストが宣言するのは
「攻撃を撃てる実行環境」までであり、攻撃の中身(ペイロード・台本・Ability定義)
は宣言しない。攻撃は無限に多様かつ環境の細部に依存するため、固定bundle化すると
環境変更のたびに攻撃を作り直す終わらない旅に入るため。

Phase4決定事項#53: 記法ガイドα版は攻撃者ノードを`attack.nodes[]`として攻撃層の
中で宣言する記法だったが、これは廃止した。攻撃者ノードは「攻撃者ロールを持つ
資産」であり環境の一部(トポロジ)である。コンテナの宣言箇所を`topology.assets`に
一元化しないと、`topology.assets`だけを見ている既存の全生成器(compose・
ルーティング・ミラーリング・ip_forwardガード・ネットワーク図)が攻撃層のノードを
静かに取りこぼす。本モジュールが扱うのは、資産そのものではなく**資産に何を
載せるか**だけである。

Phase4決定事項#58: Calderaは既定エンジンであって強制ではない(Phase0決定事項#3)。
`attack`層も`engine.caldera`も任意であり、宣言が無ければ攻撃関連の生成を一切
行わない。攻撃者ロールの資産だけを置いて素のスクリプトを撃つ運用(前身
`ot-ids-verum`の`external_attacker`/`red-team`の使い方)が、追加宣言なしで成立する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional

from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from .topology import Topology


class CalderaEngine(BaseModel):
    """Caldera server の配線(Phase0決定事項#3の最低ライン①③)。

    server自身は`topology.assets`に通常の資産として宣言し、ここでは`host`で
    名前参照するだけにする(決定事項#53の一元化)。Ability/Adversaryは
    マニフェスト外の資産であり、パスを指すだけで中身は管理しない
    (Phase0決定事項#3の最低ライン③)。
    """

    host: str
    abilities_path: Optional[str] = None
    adversaries_path: Optional[str] = None


class CalderaAgent(BaseModel):
    """攻撃ノードへのagent仕込み(Phase0決定事項#3の最低ライン②)。
    `host`は`topology.assets`の資産名を指す。
    """

    host: str
    type: Literal["sandcat"] = "sandcat"


class AttackEngine(BaseModel):
    caldera: Optional[CalderaEngine] = None


class Attack(BaseModel):
    engine: Optional[AttackEngine] = None
    agents: list[CalderaAgent] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_agents(self) -> "Attack":
        hosts = [a.host for a in self.agents]
        if len(hosts) != len(set(hosts)):
            dupes = {h for h in hosts if hosts.count(h) > 1}
            raise ValueError(
                f"duplicate agent host(s) in attack.agents: {sorted(dupes)}"
            )
        if self.agents and (self.engine is None or self.engine.caldera is None):
            raise ValueError(
                "attack.agents requires attack.engine.caldera to be declared "
                "(an agent needs a server to report to)"
            )
        return self

    def caldera_host(self) -> Optional[str]:
        if self.engine is None or self.engine.caldera is None:
            return None
        return self.engine.caldera.host

    def agent_for_host(self, asset_name: str) -> Optional[CalderaAgent]:
        for agent in self.agents:
            if agent.host == asset_name:
                return agent
        return None


def validate_attack(attack: Attack, topology: Topology) -> None:
    """Manifest側の相互参照バリデーションから呼ばれる。`host`が実在の資産を
    指しているかを検証する(決定事項#53・#58)。
    """
    asset_names = {a.name for a in topology.assets}

    if attack.engine is not None and attack.engine.caldera is not None:
        caldera_host = attack.engine.caldera.host
        if caldera_host not in asset_names:
            raise ValueError(
                f"attack.engine.caldera.host '{caldera_host}' does not reference "
                f"a defined asset"
            )
        host_asset = topology.asset_by_name(caldera_host)
        if host_asset.role != "attack-engine":
            raise ValueError(
                f"attack.engine.caldera.host '{caldera_host}' must have role "
                f"'attack-engine' (has '{host_asset.role}')"
            )

    for agent in attack.agents:
        if agent.host not in asset_names:
            raise ValueError(
                f"attack.agents host '{agent.host}' does not reference a defined asset"
            )

"""マニフェストのattack層から、Caldera統合の配線を生成する(Phase4)。

Phase0決定事項#3が定めた「最低限Calderaが使える状態」の3点を実装する:
  ① server: `attack-engine`ロールの通常資産として宣言され、attack層は`host`で
     参照するだけ(決定事項#53の一元化)。本モジュールはAbility/Adversaryの
     マウントを担う。
  ② agent: 攻撃者ノードへagentを仕込む(`agents[]`宣言から導入コマンドを合成)。
  ③ Ability/Adversary: 外部パスを読み取り専用マウント(Phase3決定事項#46と
     同じ絶対パス方式)。

決定事項#58: `attack`層も`engine.caldera`も任意。宣言が無ければ攻撃関連の生成を
一切行わない(素のスクリプトを撃つ運用が追加宣言なしで成立する)。
"""

from __future__ import annotations

from schema import Attack, Manifest

# Calderaコンテナ内で、Ability/Adversaryを読み込む標準的なパス。
# (公式Calderaのプラグイン配置に合わせた既定。将来イメージが変われば見直す。)
CALDERA_ABILITIES_DIR = "/app/caldera_assets/abilities"
CALDERA_ADVERSARIES_DIR = "/app/caldera_assets/adversaries"

# sandcat agentを取得・起動する既定コマンド。Caldera serverが配布する
# デリバリ用エンドポイントからagentバイナリを取得する定番の手順。
# server_hostはCaldera serverの資産名(Compose上のサービス名でDNS解決される)。
_SANDCAT_TEMPLATE = (
    "server=http://{server_host}:8888; "
    "curl -s -X POST -H 'file:sandcat.go' -H 'platform:linux' "
    "$server/file/download > /tmp/sandcat && chmod +x /tmp/sandcat && "
    "/tmp/sandcat -server $server -group red"
)


class AttackGenerationError(Exception):
    """攻撃層生成時のエラー。"""


def caldera_volume_mounts(manifest: Manifest, attack: Attack, asset_name: str) -> list[str]:
    """指定資産がCaldera serverの場合、Ability/Adversaryディレクトリの読み取り
    専用マウントを返す。ホスト側は絶対パスに解決する(決定事項#46)。
    """
    if attack.engine is None or attack.engine.caldera is None:
        return []
    caldera = attack.engine.caldera
    if caldera.host != asset_name:
        return []

    mounts: list[str] = []
    if caldera.abilities_path is not None:
        host_path = manifest.resolve_path(caldera.abilities_path)
        if not host_path.is_dir():
            raise AttackGenerationError(
                f"attack.engine.caldera.abilities_path not found: {host_path} "
                f"(declared as '{caldera.abilities_path}')"
            )
        mounts.append(f"{host_path.as_posix()}:{CALDERA_ABILITIES_DIR}:ro")
    if caldera.adversaries_path is not None:
        host_path = manifest.resolve_path(caldera.adversaries_path)
        if not host_path.is_dir():
            raise AttackGenerationError(
                f"attack.engine.caldera.adversaries_path not found: {host_path} "
                f"(declared as '{caldera.adversaries_path}')"
            )
        mounts.append(f"{host_path.as_posix()}:{CALDERA_ADVERSARIES_DIR}:ro")
    return mounts


def generate_agent_commands(attack: Attack, asset_name: str) -> list[str]:
    """指定資産にagentを仕込む宣言(agents[])があれば、agent取得・起動の
    コマンド列を返す。無ければ空リスト。

    既知の制約(Phase4の最小スコープ): agent起動は`&`でバックグラウンド化せず
    フォアグラウンドで動かす前提。攻撃者ノードは通常overrides.commandで自前の
    待機/実行を持つが、agentを仕込む場合はagentが主プロセスになる想定。
    複数プロセスの共存が必要になった時点でサブシェル化を検討する。
    """
    agent = attack.agent_for_host(asset_name)
    if agent is None:
        return []

    server_host = attack.caldera_host()
    if server_host is None:
        # スキーマ側(attack.py の _validate_agents)で弾かれているはずだが、
        # 生成器単体で呼ばれた場合の保険。
        raise AttackGenerationError(
            f"agent on '{asset_name}' declared but no caldera server host is set"
        )

    if agent.type == "sandcat":
        return [_SANDCAT_TEMPLATE.format(server_host=server_host)]

    raise AttackGenerationError(f"unsupported agent type: {agent.type}")

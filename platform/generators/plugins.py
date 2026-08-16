"""マニフェストのdetection層から、検知プラグイン(sidecar)の配線を生成する(Phase4)。

Phase3で`structurer`資産に対して行ったこと——スクリプトを読み取り専用で
マウントし、依存を導入し、実行コマンドを合成する——を、`host`で指定された
任意の資産へ一般化したものが本モジュールである(Phase4-DetectionAttack.md 3節)。

前身`ot-ids-verum`のsidecarが必要としていた要素は、以下の通りすべて天沼矛の
既存機構でまかなえる。Phase4で新規に作るのは「プラグイン宣言 → 組み立て」の
対応付けだけである:
  image/networks       → トポロジ層(Phase1)
  cap_add/sysctls      → ロールプリセット(Phase1決定事項#15)
  ip_forward=0         → 自動付与(Phase1決定事項#19)
  environment          → overrides.environment(Phase3決定事項#48)+本モジュール
  スクリプトのマウント → Phase3決定事項#46と同じ絶対パス方式
  起動コマンド合成     → Phase1決定事項#22・Phase3決定事項#45

決定事項#56: 依存は`requires`宣言で受け取り、生の`pip install`はマニフェストに
書かせない。決定事項#57: 接続情報は`config`宣言から環境変数として注入し、
プラグイン側が投入先をハードコードしなくて済むようにする(前身の
killchain_eql_poller.pyは`ES_URL`をスクリプト内に直書きしていた)。
"""

from __future__ import annotations

from pathlib import Path

from schema import Detection, DetectionPlugin, Manifest

# プラグイン本体をマウントするコンテナ内ディレクトリ。
PLUGIN_CONTAINER_DIR = "/app/plugins"


class PluginGenerationError(Exception):
    """検知プラグイン生成時のエラー(ソース不在・設定衝突等)。"""


def _container_path(plugin: DetectionPlugin) -> str:
    """コンテナ内でのプラグイン本体のパス。

    ソースのファイル名ではなくプラグイン名を採用する。プラグイン名は一意性が
    検証済み(detection.pyのバリデータ)なので、別ディレクトリにある同名ファイル
    (例: 複数シナリオの`main.py`)を同じホストへ載せても衝突しない。
    """
    suffix = Path(plugin.source).suffix
    return f"{PLUGIN_CONTAINER_DIR}/{plugin.name}{suffix}"


def plugin_volume_mounts(
    manifest: Manifest, detection: Detection, asset_name: str
) -> list[str]:
    """指定資産に載るプラグイン本体の、読み取り専用ボリュームマウント指定。

    ホスト側は絶対パスに解決する(生成された docker-compose.yml の設置場所に
    依存させないため、Phase3決定事項#46と同じ方針)。相対パスはマニフェスト
    自身の位置を基点に解決する(決定事項#60)。
    """
    mounts: list[str] = []
    for plugin in detection.plugins_for_host(asset_name):
        host_path = manifest.resolve_path(plugin.source)
        if not host_path.is_file():
            raise PluginGenerationError(
                f"detection.plugins['{plugin.name}'].source not found: {host_path} "
                f"(declared as '{plugin.source}')"
            )
        mounts.append(f"{host_path.as_posix()}:{_container_path(plugin)}:ro")
    return mounts


def plugin_environment(detection: Detection, asset_name: str) -> list[str]:
    """指定資産に載るプラグインの`config`を、Compose の environment 記法
    (`KEY=VALUE`)へ変換する(決定事項#57)。

    同じホストに載る複数プラグインが同じキーに異なる値を要求した場合は、
    どちらが勝つかが暗黙になるためエラーにする(環境変数はプロセス単位ではなく
    コンテナ単位で効くため、片方が意図しない値で動いてしまう)。
    """
    merged: dict[str, str] = {}
    origin: dict[str, str] = {}

    for plugin in detection.plugins_for_host(asset_name):
        for key, value in plugin.config.items():
            if key in merged and merged[key] != value:
                raise PluginGenerationError(
                    f"conflicting config '{key}' on host '{asset_name}': "
                    f"plugin '{origin[key]}' sets '{merged[key]}' but plugin "
                    f"'{plugin.name}' sets '{value}'"
                )
            merged[key] = value
            origin[key] = plugin.name

    return [f"{k}={v}" for k, v in merged.items()]


def generate_plugin_commands(detection: Detection, asset_name: str) -> list[str]:
    """指定資産の起動コマンドへ追加する、検知プラグイン起動のコマンド列を返す。
    載るプラグインが無ければ空リスト。

    既知の制約(Phase4の最小スコープ): `sidecar`型のプラグインはPython製である
    ことを前提とする(`requires`をpipで導入し、`python3`で実行する)。Phase3の
    `structurer`がDebian系イメージ限定である(決定事項#44)のと同種の割り切り。
    """
    plugins = detection.plugins_for_host(asset_name)
    if not plugins:
        return []

    commands: list[str] = []

    # 依存は全プラグイン分をまとめて1回のpipで導入する(プラグインごとに
    # pipを起動すると、同じ依存を何度も解決し起動が遅くなるため)。
    requires: list[str] = []
    for plugin in plugins:
        for pkg in plugin.requires:
            if pkg not in requires:
                requires.append(pkg)
    if requires:
        commands.append(f"pip install --quiet --no-cache-dir {' '.join(requires)}")

    # 各プラグインはバックグラウンドで並行起動し、全体を1個のサブシェルに
    # まとめる。呼び出し元(compose.py)がコマンド列を`&&`で連結するため、
    # 末尾が`&`の要素を個別に返すと不正な構文になる(Phase3決定事項#47、
    # 罠ログ#010でPhase3が実際に踏んだもの)。
    launches = [f"python3 {_container_path(p)} &" for p in plugins]
    commands.append(f"( {' '.join(launches)} wait )")
    return commands

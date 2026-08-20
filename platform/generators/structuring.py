"""マニフェストのstructuring層から、tshark+バルクローダーのコマンド列を
生成する(Phase3)。

構造化パイプラインの実行主体は`structurer`ロールの資産(決定事項#41)。
`instrumentation.mirror_to`セグメントに接続している前提で、**自分自身の
そのセグメント上のIP**からインターフェース名を動的に解決する(決定事項#29
と同じ原則。ゲートウェイのIPではなく、structurer自身のIPを使う点が
mirroring.pyとの違い——structurerはマルチホームであり、宣言順とDockerの
実際のインターフェース番号付けが一致する保証はない、前身`ot-ids-verum`
決定事項#17〔副次的発見1〕の教訓)。

決定事項#39: 1プロトコル=1専用tsharkプロセス=1専用indexという単純な対応。
決定事項#40: Elasticsearchへの投入は軽量な自前ラッパー(assets/bulk_loader.py)
で行う。プロトコル解釈・フィールド加工はtshark自身の`-T ek`出力に委ねる。
"""

from __future__ import annotations

from pathlib import Path

from schema import Asset, Instrumentation, Structuring

from .shell import resolve_interface_snippet

# structurer資産の起動コマンド内で、常にこのコンテナ内パスにマウントされる
# 前提で参照する(generators/compose.pyがボリューム設定を担当する)。
BULK_LOADER_CONTAINER_PATH = "/app/bulk_loader.py"

# ホスト側の実体(コンテナへマウントする元ファイル)。
BULK_LOADER_HOST_PATH = (Path(__file__).resolve().parent / "assets" / "bulk_loader.py")

# tshark導入(Phase3決定事項#44)。tshark自体は非対話インストール時に
# 「非rootユーザーにキャプチャ権限を与えるか」を尋ねるプロンプトを持つため、
# DEBIAN_FRONTEND=noninteractiveが無いとapt-getがハングする。Phase3の
# 最小スコープではDebian系ベースイメージのみを対象とする(Phase1決定事項#21
# のapt/apk自動判定はiproute2向けであり、tsharkのAlpine版パッケージ有無・
# 挙動差は未検証のため、既知の制約として明記する)。
_INSTALL_STRUCTURING_DEPS = (
    "DEBIAN_FRONTEND=noninteractive apt-get update -qq && "
    "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq tshark python3 "
    ">/dev/null 2>&1"
)


class StructuringGenerationError(Exception):
    """構造化パイプライン生成時のエラー(structurerのIP未設定等)。"""


def generate_structuring_commands(
    structurer: Asset, instrumentation: Instrumentation, structuring: Structuring
) -> list[str]:
    """structurer資産自身の起動コマンドに追加する、tshark+バルクローダーの
    コマンド列を返す。プロトコルが1件も宣言されていなければ空リスト
    (構造化パイプラインを起動する意味が無いため)。
    """
    if not structuring.protocols:
        return []

    own_ip = structurer.ip_on_segment(instrumentation.mirror_to)
    if own_ip is None:
        raise StructuringGenerationError(
            f"structurer asset '{structurer.name}' has no static ip on "
            f"instrumentation.mirror_to segment '{instrumentation.mirror_to}'; "
            f"structuring generation requires a fixed ip there"
        )

    commands: list[str] = [
        _INSTALL_STRUCTURING_DEPS,
        resolve_interface_snippet("STRUCT_IF", own_ip),
    ]

    # 各プロトコルのtshark|bulk_loaderパイプラインはバックグラウンド(&)で
    # 並行起動する。呼び出し元(compose.py)は生成したコマンド列全体を`&&`で
    # 連結するため、末尾が`&`の要素をそのまま個別のリスト項目にすると
    # `cmd &" && "wait`という不正な構文になる(罠ログ#010)。さらに、
    # `X && Y && Z1 & Z2 & wait`という形は`Z1`までの連結全体が1つの
    # バックグラウンドジョブとして扱われるため、`Z2`が`STRUCT_IF`解決(Y)を
    # 待たずに走ってしまう危険もある(プロトコル2件以上で顕在化)。
    # 対策として、全パイプライン起動+waitを1個のサブシェルにまとめ、
    # それ全体を単一のコマンド列要素として返す(内部は`&&`と衝突しない
    # 空白区切り。決定事項#47)。
    # Phase 9.5 決定事項#141: tsharkの表示フィルタ(proto.name)として `_ws.malformed`
    # (パケット破損) が指定された場合も、同様に `-Y "_ws.malformed"` として捉え、
    # 破損パケットのログを `ot-logs-malformed-*` 等のインデックスへ集約・検知転用する。
    #
    # Phase11 決定事項#160: decryption.tls.keylog_file が宣言されている場合、
    # tshark コマンドに `-o tls.keylog_file:...` を追加し、TLS セッションをリアルタイム
    # に復号する。これにより統裁者・SIEM 側では L7 平文を観測できる（演習用
    # 暗号鍵注入アーキテクチャ）。decryption 非宣言時は一切影響しない。
    tls_opts: list[str] = []
    if structuring.decryption is not None:
        if structuring.decryption.keylog_file:
            tls_opts.append(f"-o tls.keylog_file:{structuring.decryption.keylog_file}")
        if structuring.decryption.server_key:
            tls_opts.append(f"-o tls.rsa_keys:{structuring.decryption.server_key}")

    tls_opt_str = (" " + " ".join(tls_opts)) if tls_opts else ""

    launches = [
        (
            # `-l`（行バッファ強制）が無いと、パイプ出力はフルバッファリング
            # （既定で数KB）される。低〜中頻度のプロトコルではバッファが
            # なかなか埋まらず、bulk_loader.pyへデータが渡らないまま
            # Elasticsearchに何も投入されない（Phase12罠、負荷試験で
            # OPC UA/DNP3が実トラフィックはあるのにESに0件のまま観測された）。
            # 「リアルタイム構造化」を謳う以上、バッファリングによる遅延・
            # 未フラッシュは許容できないため常に付与する。
            f'tshark -i $STRUCT_IF -T ek -Y "{proto.name}"{tls_opt_str} -l | '
            f"python3 {BULK_LOADER_CONTAINER_PATH} "
            f'--index "{proto.output_index}" '
            f'--es-url "{structuring.elasticsearch_url}" &'
        )
        for proto in structuring.protocols
    ]
    commands.append(f"( {' '.join(launches)} wait )")
    return commands


"""マニフェストの構造化層(structuring)を表す Pydantic モデル。

Phase3決定事項#39: 1プロトコル=1専用tsharkプロセス=1専用indexという単純な
対応とする(前身ot-ids-verum決定事項#49「1プロトコル=1専用source/sink」の
再現)。決定事項#42: exceptions(Spicy/Zeek sidecar経由の例外)はPhase3では
型定義のみで、生成ロジックは実装しない。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ProtocolMapping(BaseModel):
    name: str
    output_index: str


class StructuringException(BaseModel):
    """tsharkでは扱えない/不都合なプロトコルを、別エンジンに委ねる例外指定。
    Phase3では`engine`の型だけ定義し、実際にsidecarを生成するロジックは
    実装しない(決定事項#42、Phase4以降のスコープ)。
    """

    protocol: str
    engine: Literal["spicy-sidecar"]
    reason: str


class TlsDecryptionConfig(BaseModel):
    """演習用 TLS 復号設定（Phase11 決定事項#160）。

    tshark の `-o tls.keylog_file` 機能を使い、SSLKEYLOGFILE 形式の鍵ログ
    からリアルタイムに TLS セッションを復号する。structurer コンテナ側で
    マウントされた鍵ファイルパスを tshark コマンドに渡す。

    keylog_file: コンテナ内パス（compose.py がボリュームマウントを自動生成する）
    server_key : RSA 秘密鍵パス（静的復号用・オプション）
    """

    keylog_file: Optional[str] = None
    server_key: Optional[str] = None


class DissectorPlugin(BaseModel):
    """カスタム Wireshark Lua dissector の配線（Phase11 決定事項#161）。

    tshark のネイティブ dissector が存在しないプロトコル（MELSEC 等）向けに、
    ホスト側の Lua ファイルを structurer コンテナの Wireshark プラグイン
    ディレクトリへマウントし、カスタム解析を有効化する。

    name     : プラグイン識別名（ログ用）
    host_path: ホスト側の .lua ファイルパス
    """

    name: str
    host_path: str


class StructurerResourceLimits(BaseModel):
    """structurerコンテナに適用するCgroups上限。

    既定値はPhase9.5で導入した安全側の1 CPU/512MiBを維持する。高負荷の
    シナリオはマニフェスト側で明示的に上書きし、プラットフォーム全体の
    安全策を無条件に緩めない（Phase12 Tier2）。
    """

    cpus: str = "1.0"
    memory: str = "512M"


class Structuring(BaseModel):
    engine: Literal["tshark"] = "tshark"
    protocols: list[ProtocolMapping] = Field(default_factory=list)
    exceptions: list[StructuringException] = Field(default_factory=list)
    # バルクローダーの投入先。Compose上のサービス名(asset.name)でのDNS解決を
    # 前提とする(決定事項#24でcontainer_nameを固定しない方針にした後も、
    # Composeはサービス名で名前解決できる)。決め打ちにせず明示宣言させる
    # ことで、Elasticsearch資産の名前が変わっても壊れないようにする
    # (Phase3決定事項#43、計画書のスキーマ骨子から実装時に判明した抜けの補完)。
    elasticsearch_url: str = "http://elasticsearch:9200"
    resources: StructurerResourceLimits = Field(default_factory=StructurerResourceLimits)

    # Phase11 Stage1C: 演習用暗号鍵注入アーキテクチャ（後方互換・全 Optional）
    # decryption を宣言すると、generators/structuring.py が tshark コマンドに
    # `-o tls.keylog_file:...` を条件付きで追加し、generators/compose.py が
    # structurer コンテナへの鍵ファイルボリュームマウントを自動生成する。
    decryption: Optional[TlsDecryptionConfig] = None
    # dissector_plugins を宣言すると、generators/compose.py が Lua ファイルを
    # Wireshark プラグインディレクトリへマウントし、tshark がカスタム解析を行う。
    dissector_plugins: list[DissectorPlugin] = Field(default_factory=list)

    # prefilter: 将来のプロトコル非依存(5-tuple/ポートベース)なeBPF事前フィルタ
    # 用の予約フィールド(決定事項#37)。Phase3では未実装のため、フィールド自体
    # をまだ定義しない(存在しないキーが来たら他の未知フィールド同様Pydantic
    # がデフォルトで無視せずエラーにする設定にはしていないため、将来追加時も
    # 後方互換になる)。

    @model_validator(mode="after")
    def _validate_no_duplicates_or_conflicts(self) -> "Structuring":
        names = [p.name for p in self.protocols]
        if len(names) != len(set(names)):
            dupes = {n for n in names if names.count(n) > 1}
            raise ValueError(
                f"duplicate protocol name(s) in structuring.protocols: {sorted(dupes)}"
            )

        exception_protocols = {e.protocol for e in self.exceptions}
        overlap = exception_protocols & set(names)
        if overlap:
            raise ValueError(
                f"protocol(s) declared in both structuring.protocols and "
                f"structuring.exceptions (must be exclusive): {sorted(overlap)}"
            )
        return self

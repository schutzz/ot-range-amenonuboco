"""マニフェストの構造化層(structuring)を表す Pydantic モデル。

Phase3決定事項#39: 1プロトコル=1専用tsharkプロセス=1専用indexという単純な
対応とする(前身ot-ids-verum決定事項#49「1プロトコル=1専用source/sink」の
再現)。決定事項#42: exceptions(Spicy/Zeek sidecar経由の例外)はPhase3では
型定義のみで、生成ロジックは実装しない。
"""

from __future__ import annotations

from typing import Literal

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

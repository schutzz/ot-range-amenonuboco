"""マニフェストの計装層(instrumentation)を表す Pydantic モデル。

Phase2決定事項#28: 観測対象はオプトアウト方式。`topology.segments`で宣言された
全セグメントが既定で観測対象になり、`exclude`に列挙したものだけが除外される。
`mirror_to`(観測用セグメント自身)も、自分自身をミラーする意味が無いため常に
暗黙の除外対象として扱う。

前身ot-ids-verumが技術的負債#3(sub_a未ミラーリング、2日間気づかれなかった実害)
で踏んだ「セグメントは追加したが観測対象への追加を忘れる」という罠を、
オプトイン方式(列挙)ではなくオプトアウト方式にすることで構造的に防ぐ
(詳細はPhase2-Instrumentation.md 2.1節)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, model_validator

# topology.py が本モジュールを(Manifest.instrumentationフィールドの型として)
# importするため、ここでtopology.pyをトップレベルでimportすると循環importになる。
# 型ヒントのみで使う(Segment/Topologyのインスタンスを生成したりisinstanceで
# 判定したりはしない)ため、TYPE_CHECKING配下に置き実行時のimportを避ける。
# `from __future__ import annotations`によりアノテーションは文字列として
# 遅延評価されるため、これで実行時エラーにはならない。
if TYPE_CHECKING:
    from .topology import Segment, Topology


class Instrumentation(BaseModel):
    mirror_to: str
    exclude: list[str] = Field(default_factory=list)

    def observed_segments(self, topology: Topology) -> list[Segment]:
        """観測対象セグメント一覧を返す(mirror_to自身とexcludeに列挙されたものを除く)。
        トポロジ側に新規セグメントが追加されても、この呼び出しだけで自動的に
        反映される(オプトアウト方式の核)。
        """
        skip = {self.mirror_to, *self.exclude}
        return [s for s in topology.segments if s.name not in skip]


class ObservabilityContract(BaseModel):
    """利用者が観測可能であることを要求するセグメントの汎用宣言。

    セグメント名が実在するか、または実際に観測対象に含まれるかという
    トポロジとの関係は、Manifestのクロスレイヤー検証で扱う。このモデルは
    その要求をプロトコル・検知器・シナリオに依存せず表現する責務だけを持つ。
    """

    required_segments: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_unique_required_segments(self) -> "ObservabilityContract":
        if len(self.required_segments) != len(set(self.required_segments)):
            raise ValueError("observability_contract.required_segments must be unique")
        return self


def validate_instrumentation(instrumentation: Instrumentation, topology: Topology) -> None:
    """Manifest側の相互参照バリデーションから呼ばれる(Instrumentation単体では
    topologyを知らないため、クロスバリデーションはManifestモデル側で行う)。
    """
    segment_names = {s.name for s in topology.segments}

    if instrumentation.mirror_to not in segment_names:
        raise ValueError(
            f"instrumentation.mirror_to '{instrumentation.mirror_to}' does not "
            f"reference a defined segment"
        )

    unknown_excludes = set(instrumentation.exclude) - segment_names
    if unknown_excludes:
        raise ValueError(
            f"instrumentation.exclude references undefined segment(s): "
            f"{sorted(unknown_excludes)}"
        )


def validate_observability_contract(
    contract: ObservabilityContract,
    instrumentation: Instrumentation | None,
    topology: Topology,
) -> None:
    """観測要求が宣言済みトポロジと計装状態に一致するか検証する。"""
    if instrumentation is None:
        raise ValueError(
            "observability_contract requires instrumentation to compute observed segments"
        )

    segment_names = {segment.name for segment in topology.segments}
    observed_segment_names = {
        segment.name for segment in instrumentation.observed_segments(topology)
    }

    for required_segment in contract.required_segments:
        if required_segment not in segment_names:
            raise ValueError(
                "observability_contract.required_segments references undefined "
                f"segment '{required_segment}'"
            )
        if required_segment not in observed_segment_names:
            raise ValueError(
                "observability_contract.required_segments requires segment "
                f"'{required_segment}', but it is not in the computed observed-segment set"
            )

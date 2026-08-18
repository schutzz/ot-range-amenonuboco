"""可視化エンジンの抽象(Phase6決定事項#80・#87)。

mirroring/structuring/plugins/attack の4つの配線ジェネレータは、いずれも
「特定資産のcomposeサービスに配線(command断片・volumes・environment)を足す」
共通構造を持つ。可視化エンジンも同じ構造だが、エンジン種別(grafana/kibana等)
で実装が分岐する点が新しい。その戻り値`ComposeServiceOverlay`は、5者共通の
「配線の抽象」として設計する(決定事項#87)。特別な器ではなくプロジェクト全体で
一貫した抽象である点が、抽象を最初から用意する判断(決定事項#80)を「形だけ」に
しないための鍵になる。

抽象の器は、当初検討した「ファイル生成」前提の器(`generated_files: dict[str,
str]`)ではなく、Docker Composeの一般語彙(environment/ports/volumes/configs/
command)にした(決定事項#80)。Dockerコンテナである限りどのエンジンも収まる
ため、後からAPI型エンジン(Kibana等、初期化スクリプトを`configs`でマウントし
`command`で起動時に叩く形)を足す際に、既存の器を作り直さずに済む。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from schema import Asset, Manifest, Visualization


class VisualizationGenerationError(Exception):
    """可視化層生成時のエラー(ダッシュボード資産の不在等)。"""


@dataclass
class GeneratedConfig:
    """Docker Composeの`configs`(トップレベル要素)1件分。生成器がその場で
    組み立てた内容をファイルとして実体化せず、`content:`でcomposeファイル内に
    インライン展開する(決定事項#84)。天沼矛の生成器は一貫してファイルI/Oを
    持たない(純粋関数)方針であり、その方針を可視化層でも維持するための選択。
    """

    content: str
    target: str  # コンテナ内マウント先の絶対パス


@dataclass
class ComposeServiceOverlay:
    """host資産のcomposeサービスへマージする配線断片。Docker Composeの
    一般語彙のみで構成し、特定エンジンのファイル形式を前提にしない。
    """

    environment: list[str] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    # config名(このサービス内で一意) -> 生成内容。compose.py側でグローバルに
    # ユニーク化してcompose全体のトップレベル`configs`へ展開する。
    configs: dict[str, GeneratedConfig] = field(default_factory=dict)
    command: str | None = None


class VisualizationEngine(ABC):
    """可視化エンジンの抽象。マニフェスト＋host資産から、そのエンジンを
    実現するためのcompose配線(ComposeServiceOverlay)を返す。
    """

    @abstractmethod
    def wire(
        self, manifest: Manifest, visualization: Visualization, host_asset: Asset
    ) -> ComposeServiceOverlay:
        ...

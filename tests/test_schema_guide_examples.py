"""公開記法ガイド(docs/manifest-schema-guide.md)の完全な例が、実際の
バリデータを通ることを保証する。

Phase3の計画突合検証で「公開ガイドが実装と食い違ったまま放置されていた」
のが最も影響の大きい負債だった(廃止した記法をガイドが載せ続けており、
Pydanticが未知キーを黙って無視するため利用者の意図と静かに乖離する)。
ガイドの完全な例を機械的に検証することで、ガイドと実装の乖離を検出する。
"""

from __future__ import annotations

import re

import pytest
import yaml

from schema.topology import Manifest


@pytest.fixture
def guide_text(repo_root):
    return (repo_root / "docs" / "manifest-schema-guide.md").read_text(encoding="utf-8")


def _extract_complete_example_yaml(guide_text: str) -> str:
    """§9(Phase6で#8可視化層挿入により#8→#9へ繰り下げ)の完全な例を抽出する。"""
    section = guide_text.split("## 9. 完全な例")[1].split("## 10.")[0]
    blocks = re.findall(r"```yaml\n(.*?)```", section, re.S)
    assert blocks, "§9 完全な例に yaml ブロックが見つからない"
    return blocks[0]


def test_complete_example_is_valid(guide_text):
    """§9 完全な例が、実際のManifestバリデータを通ること。"""
    raw = yaml.safe_load(_extract_complete_example_yaml(guide_text))
    Manifest.model_validate(raw)


def test_guide_has_no_retired_syntax(guide_text):
    """廃止した記法がガイドに残っていないこと。

    - `evaluation_harness`(決定事項#77で削除)
    - `attack.nodes`(決定事項#53で廃止、topology.assetsへ一元化)
    - `vector-transform`(決定事項#55、sidecarのみ実装)を「使える型」として
      案内していないこと(理由説明として言及するのは可なので、コードブロック内
      のみを対象にする)
    """
    assert "evaluation_harness" not in guide_text, "廃止した evaluation_harness が残存"

    # コードブロック(```yaml ... ```)内だけを対象に、廃止記法を探す。
    code_blocks = re.findall(r"```yaml\n(.*?)```", guide_text, re.S)
    joined = "\n".join(code_blocks)
    assert "nodes:" not in joined, "廃止した attack.nodes 記法がコード例に残存"
    assert "vector-transform" not in joined, "未実装の vector-transform がコード例に残存"

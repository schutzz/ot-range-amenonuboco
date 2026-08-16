"""マニフェスト(YAML)を読み込み、Manifest モデルへバリデーションする。"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .topology import Manifest


class ManifestLoadError(Exception):
    """マニフェストの読み込み・バリデーション失敗。"""


def load_manifest(path: str | Path) -> Manifest:
    p = Path(path)
    if not p.is_file():
        raise ManifestLoadError(f"manifest file not found: {p}")

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ManifestLoadError(f"failed to parse YAML in {p}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ManifestLoadError(f"manifest {p} did not parse to a mapping (got {type(raw).__name__})")

    try:
        manifest = Manifest.model_validate(raw)
    except ValidationError as exc:
        raise ManifestLoadError(f"manifest {p} failed validation:\n{exc}") from exc

    # マニフェスト内の相対パス(外部資産への参照)の解決基点を記録する。
    # 相対パスは「マニフェストからの相対」として書けるのが自然であり、
    # プロビジョナを実行したカレントディレクトリに依存させない(決定事項#60)。
    manifest.source_dir = p.resolve().parent
    return manifest

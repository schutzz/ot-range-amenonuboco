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
        return Manifest.model_validate(raw)
    except ValidationError as exc:
        raise ManifestLoadError(f"manifest {p} failed validation:\n{exc}") from exc

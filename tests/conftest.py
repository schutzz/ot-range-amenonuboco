"""pytest共通設定。platform/ をimportパスに通し、共有フィクスチャを提供する。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PLATFORM = _REPO_ROOT / "platform"

# platform/ はパッケージ化していない(cli.pyがsys.path.insertする運用、Phase1)。
# テストからも同じ形でimportできるようにする。
if str(_PLATFORM) not in sys.path:
    sys.path.insert(0, str(_PLATFORM))


@pytest.fixture
def repo_root() -> Path:
    return _REPO_ROOT


@pytest.fixture
def reference_manifest_path(repo_root: Path) -> Path:
    return repo_root / "manifests" / "power-grid-reference.yaml"


@pytest.fixture
def presets(repo_root: Path):
    from schema import load_role_presets

    return load_role_presets(repo_root / "platform" / "presets" / "roles.yaml")


@pytest.fixture
def reference_manifest(reference_manifest_path: Path):
    from schema import load_manifest

    return load_manifest(reference_manifest_path)

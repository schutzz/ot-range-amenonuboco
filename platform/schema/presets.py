"""ロールプリセット(platform/presets/roles.yaml)のモデル・ロード・合成ロジック。

Phase1決定事項#15: 実行属性(cap_add/sysctls)はロールごとの既定値を持ち、
asset.overrides で明示指定された値だけがそれを置き換える(加算ではない)。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from .topology import Asset, AssetRole

_DEFAULT_PRESETS_PATH = Path(__file__).resolve().parent.parent / "presets" / "roles.yaml"


class PresetLoadError(Exception):
    """ロールプリセットの読み込み・バリデーション失敗。"""


class RolePreset(BaseModel):
    cap_add: list[str] = Field(default_factory=list)
    sysctls: list[str] = Field(default_factory=list)
    # ベアOSイメージ前提のロール(l3-router等)向けの既定起動コマンド。
    # overrides.command が無い場合にのみ使われる(Phase1決定事項#23)。
    # アプリ本体を持つイメージ(elasticsearch/vector等)を使うロールでは
    # 空のままにし、ベースイメージ自身のENTRYPOINT/CMDを尊重する。
    default_command: str | None = None


class RolePresets(BaseModel):
    roles: dict[AssetRole, RolePreset]


class ResolvedAttributes(BaseModel):
    """資産1件について、ロールプリセットと overrides を合成した最終的な実行属性。"""

    cap_add: list[str] = Field(default_factory=list)
    sysctls: list[str] = Field(default_factory=list)
    ports: list[str] = Field(default_factory=list)
    command: str | None = None
    environment: list[str] = Field(default_factory=list)


def load_role_presets(path: str | Path = _DEFAULT_PRESETS_PATH) -> RolePresets:
    p = Path(path)
    if not p.is_file():
        raise PresetLoadError(f"role presets file not found: {p}")

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PresetLoadError(f"failed to parse YAML in {p}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PresetLoadError(f"{p} did not parse to a mapping (got {type(raw).__name__})")

    try:
        return RolePresets.model_validate(raw)
    except ValidationError as exc:
        raise PresetLoadError(f"{p} failed validation:\n{exc}") from exc


def resolve_effective_attributes(asset: Asset, presets: RolePresets) -> ResolvedAttributes:
    """asset.role のプリセットに asset.overrides を合成する。

    合成規則(意図的に単純化、Phase0決定事項#10):
    - cap_add / sysctls は、overrides 側で指定されていればプリセットを完全に
      置き換える(加算ではない)。プリセットの内容も残したい場合は、overrides
      側にプリセットの値ごと列挙する。曖昧な部分マージを避けるための単純化。
    - ports / command はプリセット側に概念が無いため、overrides の値をそのまま使う。
    """

    if asset.role not in presets.roles:
        raise PresetLoadError(
            f"asset '{asset.name}': no preset defined for role '{asset.role}'"
        )
    preset = presets.roles[asset.role]

    cap_add = (
        asset.overrides.cap_add
        if asset.overrides.cap_add is not None
        else list(preset.cap_add)
    )
    sysctls = (
        asset.overrides.sysctls
        if asset.overrides.sysctls is not None
        else list(preset.sysctls)
    )

    command = (
        asset.overrides.command
        if asset.overrides.command is not None
        else preset.default_command
    )

    return ResolvedAttributes(
        cap_add=cap_add,
        sysctls=sysctls,
        ports=list(asset.overrides.ports),
        command=command,
        environment=list(asset.overrides.environment),
    )

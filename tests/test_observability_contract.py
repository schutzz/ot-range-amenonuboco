"""汎用Observability Contractのschema・CLI回帰テスト。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from schema import ManifestLoadError, load_manifest


_FIXTURES = Path(__file__).parent / "fixtures" / "observability-contract"


def _fixture(name: str) -> Path:
    return _FIXTURES / f"{name}.yaml"


def _run_validate(repo_root: Path, fixture: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "platform/cli.py",
            "validate",
            str(fixture.relative_to(repo_root)),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def test_accepts_required_segment_in_computed_observed_set():
    manifest = load_manifest(_fixture("valid"))
    assert manifest.observability_contract is not None
    assert manifest.observability_contract.required_segments == ["control"]


@pytest.mark.parametrize(
    ("name", "required_text"),
    [
        ("excluded", "computed observed-segment set"),
        ("undefined", "undefined segment 'missing'"),
        ("no-instrumentation", "requires instrumentation"),
    ],
)
def test_rejects_invalid_contract_at_manifest_validation(name: str, required_text: str):
    with pytest.raises(ManifestLoadError) as exc_info:
        load_manifest(_fixture(name))

    message = str(exc_info.value)
    assert "observability_contract" in message
    assert required_text in message


def test_validate_cli_accepts_valid_contract(repo_root: Path):
    result = _run_validate(repo_root, _fixture("valid"))

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.startswith("valid:")


@pytest.mark.parametrize(
    ("name", "required_text"),
    [
        ("excluded", "control"),
        ("undefined", "missing"),
        ("no-instrumentation", "observability_contract"),
    ],
)
def test_validate_cli_rejects_invalid_contracts(
    repo_root: Path, name: str, required_text: str
):
    result = _run_validate(repo_root, _fixture(name))

    assert result.returncode != 0
    assert result.stdout == ""
    assert "error:" in result.stderr
    assert required_text in result.stderr

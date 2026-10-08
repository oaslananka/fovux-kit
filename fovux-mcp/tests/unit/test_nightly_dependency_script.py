"""Regression checks for the nightly security and compatibility workflow."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "fovux-mcp" / "scripts" / "test_with_latest_deps.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "nightly-compat.yml"


def test_latest_development_dependencies_are_binary_only() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'uv pip install --no-build --upgrade -e ".[dev]"' in script
    assert "uv sync --upgrade --extra dev" not in script


def test_latest_development_tests_cannot_rewrite_lockfile() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "uv run --no-sync --no-build pytest" in script


def test_latest_deps_workflow_triggers_when_security_script_changes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert '"fovux-mcp/scripts/test_with_latest_deps.sh"' in workflow
    assert '"fovux-mcp/tests/unit/test_nightly_dependency_script.py"' in workflow


def test_optional_ml_compatibility_preserves_binary_only_policy() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "uv sync --frozen --extra dev --extra yolo --no-install-project --no-build" in workflow
    assert "uv run --no-sync --no-build pytest" in workflow


def test_latest_dependencies_are_checked_on_both_python_versions() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'python-version: ["3.13", "3.14"]' in workflow

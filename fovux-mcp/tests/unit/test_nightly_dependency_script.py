"""Regression checks for the nightly security and compatibility workflow."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "fovux-mcp" / "scripts" / "test_with_latest_deps.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "nightly-compat.yml"


def test_latest_development_dependencies_are_binary_only() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert re.search(
        r"""uv\s+pip\s+install\s+--no-build\s+--upgrade\s+-e\s+["']?\.\[dev\]["']?""",
        script,
    ), "Nightly installer must disable source builds for the latest dev extra"
    assert not re.search(r"uv\s+sync\s+--upgrade\s+--extra\s+dev", script)


def test_latest_development_tests_cannot_rewrite_lockfile() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"uv\s+run\s+--no-sync\s+--no-build\s+pytest", script)


def test_latest_deps_workflow_triggers_when_security_script_changes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for path in (
        "fovux-mcp/scripts/test_with_latest_deps.sh",
        "fovux-mcp/tests/unit/test_nightly_dependency_script.py",
    ):
        assert re.search(
            rf"""(?m)^\s*-\s*["']?{re.escape(path)}["']?\s*$""",
            workflow,
        ), f"Nightly workflow missing path trigger: {path}"


def test_optional_ml_compatibility_preserves_binary_only_policy() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(
        r"uv\s+sync\s+--frozen\s+--extra\s+dev\s+--extra\s+yolo\s+--no-install-project\s+--no-build",
        workflow,
    )
    assert re.search(r"uv\s+run\s+--no-sync\s+--no-build\s+pytest", workflow)


def test_latest_dependencies_are_checked_on_both_python_versions() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(
        r"""python-version:\s*\[\s*["']?3\.13["']?\s*,\s*["']?3\.14["']?\s*\]""",
        workflow,
    )

#!/usr/bin/env python3
"""Regression tests for nightly dependency compatibility script."""

import os
import subprocess
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "test_with_latest_deps.sh"
WORKFLOW_PATH = Path(__file__).parent.parent.parent.parent / ".github" / "workflows" / "nightly-compat.yml"


class TestNightlyDependencyScript:
    """Tests for the nightly dependency compatibility script."""

    def test_script_exists(self):
        """Verify the script file exists."""
        assert SCRIPT_PATH.exists(), f"Script not found at {SCRIPT_PATH}"

    def test_script_is_executable(self):
        """Verify the script is executable."""
        assert os.access(SCRIPT_PATH, os.X_OK), f"Script at {SCRIPT_PATH} is not executable"

    def test_bash_syntax_valid(self):
        """Verify the script has valid bash syntax."""
        result = subprocess.run(["bash", "-n", str(SCRIPT_PATH)], capture_output=True, text=True)
        assert result.returncode == 0, f"Bash syntax error: {result.stderr}"

    def test_uv_sync_uses_no_build_flag(self):
        """Verify uv sync command uses --no-build flag."""
        content = SCRIPT_PATH.read_text()
        assert "uv sync --upgrade --extra dev --no-build" in content, (
            "uv sync command must include --no-build flag"
        )

    def test_uv_run_uses_no_build_flag(self):
        """Verify uv run command uses --no-build flag."""
        content = SCRIPT_PATH.read_text()
        assert "uv run --no-sync --no-build" in content, (
            "uv run command must include --no-build flag"
        )

    def test_lockfile_restoration_via_trap(self):
        """Verify lockfile restoration is handled via trap on EXIT."""
        content = SCRIPT_PATH.read_text()
        assert "trap cleanup EXIT" in content, "Script must have trap cleanup on EXIT"
        assert "cleanup()" in content, "Script must define cleanup function"
        assert "mv \"$BACKUP_LOCKFILE\" \"$LOCKFILE\"" in content, "Cleanup must restore lockfile"

    def test_workflow_triggers_on_script_changes(self):
        """Verify workflow triggers when script changes."""
        content = WORKFLOW_PATH.read_text()
        assert "fovux-mcp/scripts/test_with_latest_deps.sh" in content, (
            "Workflow must trigger on script changes"
        )

    def test_workflow_triggers_on_test_changes(self):
        """Verify workflow triggers when this test file changes."""
        content = WORKFLOW_PATH.read_text()
        assert "fovux-mcp/tests/unit/test_nightly_dependency_script.py" in content, (
            "Workflow must trigger on test file changes"
        )

    def test_workflow_runs_on_python_313_and_314(self):
        """Verify workflow runs on Python 3.13 and 3.14."""
        content = WORKFLOW_PATH.read_text()
        assert '"3.13"' in content, "Workflow must run on Python 3.13"
        assert '"3.14"' in content, "Workflow must run on Python 3.14"

    def test_optional_ml_job_uses_no_install_project_no_build(self):
        """Verify optional ML job uses --no-install-project --no-build."""
        content = WORKFLOW_PATH.read_text()
        assert "uv sync --frozen --extra dev --extra yolo --no-install-project --no-build" in content, (
            "Optional ML job must use --no-install-project --no-build"
        )
        assert "uv run --no-sync --no-build" in content, (
            "Optional ML job must use --no-build in uv run"
        )
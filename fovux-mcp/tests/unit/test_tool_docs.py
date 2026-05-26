"""Tests for scripts/check_tool_docs.py documentation completeness."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.path_helpers import find_package_root

REPO_ROOT = find_package_root(Path(__file__))
CHECK_TOOL_DOCS = REPO_ROOT / "scripts" / "check_tool_docs.py"


def test_check_tool_docs_exits_zero() -> None:
    """All registered tools have documentation pages."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(CHECK_TOOL_DOCS)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"check_tool_docs.py found missing docs:\n{result.stdout}\n{result.stderr}"
    )

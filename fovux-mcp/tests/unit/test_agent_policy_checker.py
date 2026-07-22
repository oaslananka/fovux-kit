"""Regression tests for the repository agent-policy checker."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKER = REPO_ROOT / "scripts" / "check_agent_policy.py"


def test_agent_policy_checker_supports_domain_route_package() -> None:
    """Policy validation must follow the current HTTP service/route ownership."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(CHECKER)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

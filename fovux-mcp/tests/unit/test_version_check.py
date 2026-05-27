"""Tests for scripts/check_versions.py version coherence checker."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.path_helpers import find_monorepo_root

REPO_ROOT = find_monorepo_root(Path(__file__))
CHECK_VERSIONS = REPO_ROOT / "scripts" / "check_versions.py"


def test_check_versions_exits_zero() -> None:
    """When all version sources are consistent, the script exits 0."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(CHECK_VERSIONS)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"check_versions.py unexpectedly failed:\n{result.stdout}\n{result.stderr}"
    )
    assert "coherent" in result.stdout.lower() or "4.1.0" in result.stdout


def test_check_versions_detects_mismatch(tmp_path: Path) -> None:
    """When a version source is tampered, the script exits 1."""
    # Create a minimal monorepo fixture with a version mismatch
    mcp_dir = tmp_path / "fovux-mcp" / "src" / "fovux"
    mcp_dir.mkdir(parents=True)

    (tmp_path / "fovux-mcp" / "pyproject.toml").write_text(
        '[project]\nname = "fovux-mcp"\nversion = "4.1.0"\n'
    )
    (tmp_path / "fovux-mcp" / "uv.lock").write_text(
        '[[package]]\nname = "fovux-mcp"\nversion = "4.1.0"\n'
    )
    (mcp_dir / "__init__.py").write_text('__version__ = "4.0.0"\n')

    studio_dir = tmp_path / "fovux-studio"
    studio_dir.mkdir()
    (studio_dir / "package.json").write_text('{"version": "4.1.0"}\n')

    (tmp_path / "fovux-mcp" / "server.json").write_text(
        '{"version": "4.1.0", "packages": [{"version": "4.1.0"}]}\n'
    )
    (tmp_path / "fovux-mcp" / "smithery.yaml").write_text('version: "4.1.0"\n')
    (tmp_path / "mcp.json").write_text('{"version": "4.1.0", "packages": [{"version": "4.1.0"}]}\n')
    (tmp_path / "fovux-mcp" / "CHANGELOG.md").write_text("# Changelog\n\n## [4.1.0] - 2026-04-27\n")
    (studio_dir / "CHANGELOG.md").write_text("# Changelog\n\n## [4.1.0] - 2026-04-27\n")

    # Copy the script and adjust its root detection
    script_content = CHECK_VERSIONS.read_text(encoding="utf-8")
    patched = script_content.replace(
        "Path(__file__).resolve().parent.parent",
        f'Path("{tmp_path.as_posix()}")',
    )
    patched_script = tmp_path / "check_versions.py"
    patched_script.write_text(patched)

    result = subprocess.run(  # noqa: S603
        [sys.executable, str(patched_script)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 1, (
        f"check_versions.py should have detected mismatch:\n{result.stdout}\n{result.stderr}"
    )
    assert "MISMATCH" in result.stdout.upper()

"""Tests for scripts/check_versions.py version coherence checker."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.path_helpers import find_monorepo_root

REPO_ROOT = find_monorepo_root(Path(__file__))
CHECK_VERSIONS = REPO_ROOT / "scripts" / "check_versions.py"


def write_version_fixture(
    root: Path,
    *,
    mcp_version: str = "4.1.0",
    mcp_init_version: str | None = None,
    studio_version: str = "1.0.0",
    studio_changelog_version: str | None = None,
) -> None:
    """Create a minimal monorepo fixture for version coherence tests."""
    mcp_init_version = mcp_init_version or mcp_version
    studio_changelog_version = studio_changelog_version or studio_version

    mcp_dir = root / "fovux-mcp" / "src" / "fovux"
    mcp_dir.mkdir(parents=True)
    studio_dir = root / "fovux-studio"
    studio_dir.mkdir()

    (root / "fovux-mcp" / "pyproject.toml").write_text(
        f'[project]\nname = "fovux-mcp"\nversion = "{mcp_version}"\n',
        encoding="utf-8",
    )
    (root / "fovux-mcp" / "uv.lock").write_text(
        f'[[package]]\nname = "fovux-mcp"\nversion = "{mcp_version}"\n',
        encoding="utf-8",
    )
    (mcp_dir / "__init__.py").write_text(
        f'__version__ = "{mcp_init_version}"\n',
        encoding="utf-8",
    )
    (studio_dir / "package.json").write_text(
        f'{{"version": "{studio_version}"}}\n',
        encoding="utf-8",
    )
    (root / "fovux-mcp" / "server.json").write_text(
        f'{{"version": "{mcp_version}", "packages": [{{"version": "{mcp_version}"}}]}}\n',
        encoding="utf-8",
    )
    (root / "fovux-mcp" / "smithery.yaml").write_text(
        f'version: "{mcp_version}"\n',
        encoding="utf-8",
    )
    (root / "mcp.json").write_text(
        f'{{"version": "{mcp_version}", "packages": [{{"version": "{mcp_version}"}}]}}\n',
        encoding="utf-8",
    )
    (root / "fovux-mcp" / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{mcp_version}] - 2026-04-27\n",
        encoding="utf-8",
    )
    (studio_dir / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{studio_changelog_version}] - 2026-04-27\n",
        encoding="utf-8",
    )


def write_patched_script(root: Path) -> Path:
    """Copy check_versions.py with root detection pointed at a fixture root."""
    script_content = CHECK_VERSIONS.read_text(encoding="utf-8")
    patched = script_content.replace(
        "Path(__file__).resolve().parent.parent",
        f'Path("{root.as_posix()}")',
    )
    patched_script = root / "check_versions.py"
    patched_script.write_text(patched, encoding="utf-8")
    return patched_script


def test_check_versions_exits_zero() -> None:
    """When each release track is consistent, the script exits 0."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(CHECK_VERSIONS)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"check_versions.py unexpectedly failed:\n{result.stdout}\n{result.stderr}"
    )
    assert "MCP version sources are coherent:" in result.stdout
    assert "Studio version sources are coherent:" in result.stdout


def test_check_versions_detects_mcp_mismatch(tmp_path: Path) -> None:
    """When an MCP version source is tampered, the script exits 1."""
    write_version_fixture(tmp_path, mcp_init_version="4.0.0")
    patched_script = write_patched_script(tmp_path)

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
    assert "MCP version sources" in result.stdout


def test_check_versions_detects_studio_mismatch(tmp_path: Path) -> None:
    """When a Studio version source is tampered, the script exits 1."""
    write_version_fixture(tmp_path, studio_changelog_version="0.9.0")
    patched_script = write_patched_script(tmp_path)

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
    assert "Studio version sources" in result.stdout

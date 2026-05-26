"""Tests for repository path discovery helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.path_helpers import find_monorepo_root, find_package_root


def test_find_package_root_skips_mutmut_copy(tmp_path: Path) -> None:
    """Mutation-test copies should not be mistaken for the real package root."""
    package_root = tmp_path / "fovux-mcp"
    copied_root = package_root / "mutants"
    test_file = copied_root / "tests" / "security" / "test_http_security.py"

    (package_root / "scripts").mkdir(parents=True)
    (package_root / "src" / "fovux").mkdir(parents=True)
    (copied_root / "src" / "fovux").mkdir(parents=True)
    test_file.parent.mkdir(parents=True)

    (package_root / "pyproject.toml").write_text('[project]\nname = "fovux-mcp"\n')
    (package_root / "Dockerfile").write_text("FROM scratch\n")
    (package_root / "scripts" / "check_tool_docs.py").write_text("print('ok')\n")
    (copied_root / "pyproject.toml").write_text('[project]\nname = "fovux-mcp"\n')
    test_file.write_text("# copied test\n")

    assert find_package_root(test_file) == package_root.resolve()


def test_find_monorepo_root_finds_repository_from_package_file(tmp_path: Path) -> None:
    monorepo_root = tmp_path / "repo"
    package_root = monorepo_root / "fovux-mcp"
    test_file = package_root / "tests" / "unit" / "test_example.py"

    (monorepo_root / "scripts").mkdir(parents=True)
    test_file.parent.mkdir(parents=True)

    (monorepo_root / "scripts" / "check_versions.py").write_text("print('ok')\n")
    (package_root / "pyproject.toml").write_text('[project]\nname = "fovux-mcp"\n')
    test_file.write_text("# test\n")

    assert find_monorepo_root(test_file) == monorepo_root.resolve()


def test_find_package_root_reports_missing_markers(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_missing.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("# test\n")

    with pytest.raises(RuntimeError) as exc_info:
        find_package_root(test_file)
    message = str(exc_info.value)
    assert "Could not locate fovux-mcp package root" in message
    assert f"start={test_file.resolve()}" in message
    assert "markers=" in message
    assert "pyproject.toml" in message
    assert "check_tool_docs.py" in message


def test_find_monorepo_root_reports_missing_markers(tmp_path: Path) -> None:
    test_file = tmp_path / "fovux-mcp" / "tests" / "test_missing.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("# test\n")

    with pytest.raises(RuntimeError) as exc_info:
        find_monorepo_root(test_file)
    message = str(exc_info.value)
    assert "Could not locate monorepo root" in message
    assert f"start={test_file.resolve()}" in message
    assert "markers=" in message
    assert "check_versions.py" in message
    assert "pyproject.toml" in message

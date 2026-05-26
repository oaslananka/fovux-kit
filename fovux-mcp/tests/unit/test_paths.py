"""Unit tests for fovux.core.paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from fovux.core.paths import FovuxPaths, ensure_fovux_dirs, get_fovux_home


def test_get_fovux_home_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """FOVUX_HOME env var should take priority."""
    custom = tmp_path / "custom_fovux"
    monkeypatch.setenv("FOVUX_HOME", str(custom))
    result = get_fovux_home()
    assert result == custom.resolve()


def test_get_fovux_home_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without env var, should default to ~/.fovux."""
    monkeypatch.delenv("FOVUX_HOME", raising=False)
    result = get_fovux_home()
    assert result.name == ".fovux"


def test_fovux_paths_structure(tmp_path: Path) -> None:
    """FovuxPaths should expose the expected subdirectory attributes."""
    paths = FovuxPaths(tmp_path)
    assert paths.runs == tmp_path / "runs"
    assert paths.models == tmp_path / "models"
    assert paths.cache == tmp_path / "cache"
    assert paths.exports == tmp_path / "exports"
    assert paths.datasets == tmp_path / "datasets"
    assert paths.runs_db == tmp_path / "runs.db"
    assert paths.config_file == tmp_path / "config.toml"


def test_ensure_fovux_dirs_creates_directories(tmp_path: Path) -> None:
    """ensure_fovux_dirs should create all required subdirectories."""
    paths = ensure_fovux_dirs(home=tmp_path)
    assert paths.runs.is_dir()
    assert paths.models.is_dir()
    assert paths.cache.is_dir()
    assert paths.exports.is_dir()
    assert paths.datasets.is_dir()


def test_run_dir(tmp_path: Path) -> None:
    """run_dir should return the correct path for a run."""
    paths = FovuxPaths(tmp_path)
    run_dir = paths.run_dir("run_2026-04-20_142301")
    assert run_dir == tmp_path / "runs" / "run_2026-04-20_142301"

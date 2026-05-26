"""Shared pytest fixtures and configuration."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def tmp_fovux_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide a temporary FOVUX_HOME directory for tests."""
    fovux_home = tmp_path / ".fovux"
    fovux_home.mkdir()
    monkeypatch.setenv("FOVUX_HOME", str(fovux_home))
    return fovux_home


@pytest.fixture()
def mini_yolo_path() -> Path:
    """Return path to the mini YOLO fixture dataset."""
    return Path(__file__).parent / "fixtures" / "mini_yolo"


@pytest.fixture()
def mini_coco_path() -> Path:
    """Return path to the mini COCO fixture dataset."""
    return Path(__file__).parent / "fixtures" / "mini_coco"


@pytest.fixture()
def corrupt_samples_path() -> Path:
    """Return path to the corrupt samples fixture."""
    return Path(__file__).parent / "fixtures" / "corrupt_samples"

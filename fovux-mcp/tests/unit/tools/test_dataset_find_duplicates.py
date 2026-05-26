"""Tests for dataset_find_duplicates."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from fovux.core.errors import FovuxDatasetNotFoundError
from fovux.schemas.dataset import DatasetFindDuplicatesInput
from fovux.tools.dataset_find_duplicates import _run_find_duplicates

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


def test_no_exact_duplicates_in_mini_yolo():
    """Distinct images in mini_yolo should produce zero exact duplicates (threshold=0)."""
    inp = DatasetFindDuplicatesInput(dataset_path=FIXTURES / "mini_yolo", hamming_threshold=0)
    out = _run_find_duplicates(inp)
    assert out.total_images > 0
    assert out.total_duplicates == 0


def test_finds_exact_duplicates(tmp_path: Path):
    """Identical images should be grouped together."""
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        img = Image.new("RGB", (64, 64), color=(100, 150, 200))
        img.save(tmp_path / name)
    inp = DatasetFindDuplicatesInput(dataset_path=tmp_path, hamming_threshold=0)
    out = _run_find_duplicates(inp)
    assert len(out.duplicate_groups) >= 1
    assert out.total_duplicates >= 2


def test_nonexistent_path_raises():
    """Should raise FovuxDatasetNotFoundError."""
    with pytest.raises(FovuxDatasetNotFoundError):
        _run_find_duplicates(DatasetFindDuplicatesInput(dataset_path=Path("/no/dataset")))


def test_duration_positive():
    """Analysis duration should be recorded."""
    inp = DatasetFindDuplicatesInput(dataset_path=FIXTURES / "mini_yolo")
    out = _run_find_duplicates(inp)
    assert out.analysis_duration_seconds > 0

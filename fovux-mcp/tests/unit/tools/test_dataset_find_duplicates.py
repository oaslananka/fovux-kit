"""Tests for dataset_find_duplicates."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from fovux.core.errors import FovuxDatasetNotFoundError, FovuxPathValidationError
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
    assert len(out.duplicate_groups) == 1
    assert out.duplicate_groups[0].hamming_distance == 0
    assert out.total_duplicates == 2
    assert out.duplicate_pct == pytest.approx(66.67)


def test_across_splits_false_does_not_group_cross_split_duplicates(tmp_path: Path):
    """Cross-split duplicate detection should honor the across_splits flag."""
    for split in ("train", "val"):
        image_dir = tmp_path / "images" / split
        image_dir.mkdir(parents=True)
        Image.new("RGB", (64, 64), color=(100, 150, 200)).save(image_dir / "same.jpg")

    within_splits = _run_find_duplicates(
        DatasetFindDuplicatesInput(
            dataset_path=tmp_path,
            hamming_threshold=0,
            across_splits=False,
        )
    )
    across_splits = _run_find_duplicates(
        DatasetFindDuplicatesInput(
            dataset_path=tmp_path,
            hamming_threshold=0,
            across_splits=True,
        )
    )

    assert within_splits.total_duplicates == 0
    assert across_splits.total_duplicates == 1


def test_across_splits_false_normalizes_common_split_aliases(tmp_path: Path):
    """Common validation aliases should not collapse into unsplit comparisons."""
    for split in ("validation", "holdout"):
        image_dir = tmp_path / "images" / split
        image_dir.mkdir(parents=True)
        Image.new("RGB", (64, 64), color=(100, 150, 200)).save(image_dir / "same.jpg")

    out = _run_find_duplicates(
        DatasetFindDuplicatesInput(
            dataset_path=tmp_path,
            hamming_threshold=0,
            across_splits=False,
        )
    )

    assert out.total_duplicates == 0


@pytest.mark.parametrize(
    "broad_root",
    [Path("~"), Path("."), Path(tempfile.gettempdir())],
)
def test_rejects_broad_recursive_scan_roots(broad_root: Path) -> None:
    """Broad roots must be rejected before the recursive image walk starts."""
    with (
        patch("fovux.tools.dataset_find_duplicates.find_images") as finder,
        pytest.raises(FovuxPathValidationError, match="dedicated dataset directory"),
    ):
        _run_find_duplicates(DatasetFindDuplicatesInput(dataset_path=broad_root))

    finder.assert_not_called()


def test_nonexistent_path_raises():
    """Should raise FovuxDatasetNotFoundError."""
    with pytest.raises(FovuxDatasetNotFoundError):
        _run_find_duplicates(DatasetFindDuplicatesInput(dataset_path=Path("/no/dataset")))


def test_duration_positive():
    """Analysis duration should be recorded."""
    inp = DatasetFindDuplicatesInput(dataset_path=FIXTURES / "mini_yolo")
    out = _run_find_duplicates(inp)
    assert out.analysis_duration_seconds > 0

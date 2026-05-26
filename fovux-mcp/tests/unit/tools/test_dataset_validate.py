"""Tests for dataset_validate."""

from __future__ import annotations

from pathlib import Path

import pytest

from fovux.core.errors import FovuxDatasetNotFoundError
from fovux.schemas.dataset import DatasetValidateInput
from fovux.tools.dataset_validate import _run_validate

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


def test_validate_mini_yolo_passes():
    """Clean mini_yolo fixture should have no errors."""
    inp = DatasetValidateInput(dataset_path=FIXTURES / "mini_yolo")
    out = _run_validate(inp)
    assert out.valid is True
    assert len(out.errors) == 0


def test_validate_summary_string():
    """Summary should contain PASS or FAIL."""
    inp = DatasetValidateInput(dataset_path=FIXTURES / "mini_yolo")
    out = _run_validate(inp)
    assert "PASS" in out.summary or "FAIL" in out.summary


def test_validate_nonexistent_path():
    """Should raise FovuxDatasetNotFoundError."""
    with pytest.raises(FovuxDatasetNotFoundError):
        _run_validate(DatasetValidateInput(dataset_path=Path("/no/such/dataset")))


def test_validate_corrupt_label(tmp_path: Path):
    """A label with out-of-bounds bbox should produce a warning or error."""
    # Create minimal YOLO dataset with bad bbox
    (tmp_path / "images" / "train").mkdir(parents=True)
    (tmp_path / "labels" / "train").mkdir(parents=True)
    from PIL import Image

    img = Image.new("RGB", (64, 64))
    img.save(tmp_path / "images" / "train" / "bad.jpg")
    # bbox with cx > 1
    (tmp_path / "labels" / "train" / "bad.txt").write_text("0 1.5 0.5 0.3 0.3\n")
    (tmp_path / "data.yaml").write_text(
        "nc: 1\nnames: ['obj']\ntrain: images/train\nval: images/val\n"
    )
    inp = DatasetValidateInput(dataset_path=tmp_path, check_bbox_bounds=True)
    out = _run_validate(inp)
    # Should flag the out-of-bounds bbox
    all_issues = out.errors + out.warnings
    assert any("out of" in i.message.lower() or "range" in i.message.lower() for i in all_issues)

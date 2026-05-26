"""Tests for dataset_convert."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fovux.core.errors import FovuxDatasetFormatError, FovuxDatasetNotFoundError
from fovux.schemas.dataset import DatasetConvertInput
from fovux.tools.dataset_convert import _run_convert

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


def test_yolo_to_coco_creates_json(tmp_path: Path):
    """YOLO→COCO conversion should produce a valid COCO JSON."""
    dst = tmp_path / "coco_out"
    out = _run_convert(
        DatasetConvertInput(
            source_path=FIXTURES / "mini_yolo",
            target_format="coco",
            target_path=dst,
            copy_images=False,
        )
    )
    assert out.target_path.exists()
    json_file = dst / "annotations" / "instances_train.json"
    assert json_file.exists()
    assert (dst / "annotations" / "instances_val.json").exists()
    data = json.loads(json_file.read_text())
    assert "images" in data
    assert "annotations" in data
    assert "categories" in data


def test_coco_to_yolo_creates_labels(tmp_path: Path):
    """COCO→YOLO conversion should produce .txt label files."""
    dst = tmp_path / "yolo_out"
    out = _run_convert(
        DatasetConvertInput(
            source_path=FIXTURES / "mini_coco",
            source_format="coco",
            target_format="yolo",
            target_path=dst,
        )
    )
    labels = list((dst / "labels").rglob("*.txt"))
    assert len(labels) > 0
    assert out.annotations_converted > 0


def test_convert_nonexistent_source_raises(tmp_path: Path):
    """Should raise FovuxDatasetNotFoundError for missing source."""
    with pytest.raises(FovuxDatasetNotFoundError):
        _run_convert(
            DatasetConvertInput(
                source_path=Path("/no/such"),
                target_format="coco",
                target_path=tmp_path / "out",
            )
        )


def test_convert_same_format_raises(tmp_path: Path):
    """Converting to the same format should raise FovuxDatasetFormatError."""
    with pytest.raises(FovuxDatasetFormatError):
        _run_convert(
            DatasetConvertInput(
                source_path=FIXTURES / "mini_yolo",
                source_format="yolo",
                target_format="yolo",
                target_path=tmp_path / "out",
            )
        )


def test_convert_duration_positive(tmp_path: Path):
    """Conversion duration should be positive."""
    out = _run_convert(
        DatasetConvertInput(
            source_path=FIXTURES / "mini_yolo",
            target_format="coco",
            target_path=tmp_path / "out",
        )
    )
    assert out.conversion_duration_seconds > 0

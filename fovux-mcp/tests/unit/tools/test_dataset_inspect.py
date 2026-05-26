"""Unit + integration tests for dataset_inspect."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from fovux.core.errors import FovuxDatasetFormatError, FovuxDatasetNotFoundError
from fovux.schemas.dataset import DatasetInspectInput
from fovux.tools.dataset_inspect import _run_inspect

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


def test_inspect_mini_yolo_counts():
    """Should detect 40 images and 2 classes in mini_yolo fixture."""
    inp = DatasetInspectInput(dataset_path=FIXTURES / "mini_yolo")
    out = _run_inspect(inp)
    assert out.format_detected == "yolo"
    assert out.total_images == 40
    assert out.num_classes == 2
    assert out.total_annotations == 40


def test_inspect_mini_yolo_class_names():
    """Class names should be cat and dog."""
    inp = DatasetInspectInput(dataset_path=FIXTURES / "mini_yolo")
    out = _run_inspect(inp)
    names = [c.name for c in out.classes]
    assert "cat" in names
    assert "dog" in names


def test_inspect_mini_yolo_splits():
    """Should detect train and val splits."""
    inp = DatasetInspectInput(dataset_path=FIXTURES / "mini_yolo")
    out = _run_inspect(inp)
    assert "train" in out.splits_detected
    assert "val" in out.splits_detected
    assert out.splits_detected["train"] == 30
    assert out.splits_detected["val"] == 10


def test_inspect_mini_coco():
    """Should inspect COCO format dataset."""
    inp = DatasetInspectInput(dataset_path=FIXTURES / "mini_coco", format="coco")
    out = _run_inspect(inp)
    assert out.format_detected == "coco"
    assert out.total_images == 20
    assert out.num_classes == 2


def test_inspect_nonexistent_path():
    """Should raise FovuxDatasetNotFoundError for missing path."""
    with pytest.raises(FovuxDatasetNotFoundError):
        _run_inspect(DatasetInspectInput(dataset_path=Path("/nonexistent/dataset")))


def test_inspect_filesystem_root_rejects_without_recursive_scan(monkeypatch: pytest.MonkeyPatch):
    """Filesystem roots should be rejected without recursively scanning the drive."""
    from fovux.core import dataset_utils

    def fail_rglob(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("recursive root scan should not be used during format detection")

    monkeypatch.setattr(Path, "rglob", fail_rglob)

    with pytest.raises(FovuxDatasetFormatError):
        dataset_utils.detect_format(Path("/").resolve())


def test_inspect_sample_paths_included():
    """include_samples=True should return up to 10 sample paths."""
    inp = DatasetInspectInput(dataset_path=FIXTURES / "mini_yolo", include_samples=True)
    out = _run_inspect(inp)
    assert len(out.sample_paths) > 0
    assert len(out.sample_paths) <= 10


def test_inspect_gini_balanced():
    """Balanced dataset should have low Gini coefficient."""
    inp = DatasetInspectInput(dataset_path=FIXTURES / "mini_yolo")
    out = _run_inspect(inp)
    assert out.class_balance_gini < 0.5


def test_inspect_duration_recorded():
    """Duration should be a positive float."""
    inp = DatasetInspectInput(dataset_path=FIXTURES / "mini_yolo")
    out = _run_inspect(inp)
    assert out.analysis_duration_seconds > 0


def test_inspect_yolo_reports_missing_labels_and_bbox_buckets(tmp_path: Path):
    """YOLO inspection should report images without labels and normalized bbox sizes."""
    dataset_path = tmp_path / "dataset"
    images_dir = dataset_path / "images" / "train"
    labels_dir = dataset_path / "labels" / "train"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    for stem in ("small", "medium", "large", "missing"):
        Image.new("RGB", (64, 64), color=(20, 20, 20)).save(images_dir / f"{stem}.jpg")
    (labels_dir / "small.txt").write_text("0 0.5 0.5 0.05 0.05\n", encoding="utf-8")
    (labels_dir / "medium.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (labels_dir / "large.txt").write_text("0 0.5 0.5 0.5 0.5\n", encoding="utf-8")
    (dataset_path / "data.yaml").write_text("names: ['object']\n", encoding="utf-8")

    out = _run_inspect(DatasetInspectInput(dataset_path=dataset_path))

    assert out.total_images == 4
    assert out.orphan_images == 1
    assert [path.name for path in out.missing_label_images] == ["missing.jpg"]
    assert out.bbox_size_buckets == {"small": 1, "medium": 1, "large": 1}

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


def test_inspect_yolo_includes_declared_classes_without_annotations(tmp_path: Path):
    """Declared but unused classes should contribute to class-balance statistics."""
    images_dir = tmp_path / "images" / "train"
    labels_dir = tmp_path / "labels" / "train"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    Image.new("RGB", (16, 16), color=(10, 20, 30)).save(images_dir / "sample.jpg")
    (labels_dir / "sample.txt").write_text("0 0.5 0.5 0.5 0.5\n", encoding="utf-8")
    (tmp_path / "data.yaml").write_text(
        "path: .\ntrain: images/train\nnc: 2\nnames: ['present', 'missing']\n",
        encoding="utf-8",
    )

    out = _run_inspect(DatasetInspectInput(dataset_path=tmp_path))

    assert out.num_classes == 2
    assert [(item.name, item.count) for item in out.classes] == [
        ("present", 1),
        ("missing", 0),
    ]
    assert out.class_balance_gini == 0.5


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


def test_inspect_quality_intelligence(tmp_path: Path):
    """Test computation of dataset quality metrics, leakage, duplicates, and fix plan."""
    # Create directories for training split
    train_images = tmp_path / "images" / "train"
    train_labels = tmp_path / "labels" / "train"
    train_images.mkdir(parents=True)
    train_labels.mkdir(parents=True)

    # Create directories for validation split (to test leakage)
    val_images = tmp_path / "images" / "val"
    val_labels = tmp_path / "labels" / "val"
    val_images.mkdir(parents=True)
    val_labels.mkdir(parents=True)

    # Save identical images to train and val (to trigger duplication/leakage)
    img_data = Image.new("RGB", (64, 64), color=(50, 50, 50))
    img_data.save(train_images / "img1.jpg")
    img_data.save(val_images / "img1.jpg")  # duplicate of img1

    # Save a normal image
    from PIL import ImageDraw

    img_data2 = Image.new("RGB", (64, 64), color=(100, 100, 100))
    draw = ImageDraw.Draw(img_data2)
    draw.line((0, 0, 64, 64), fill=(0, 255, 0), width=3)
    img_data2.save(train_images / "img2.jpg")

    # Bounding boxes for train/img1 (normal)
    (train_labels / "img1.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")

    # Bounding boxes for val/img1 (has anomalies: out-of-bounds, tiny, overlapping)
    # 0: normal
    # 1: out-of-bounds cx=1.2 (escaping limits)
    # 2: tiny w=0.001, h=0.001 (w*h < 0.0005)
    # 3: overlapping with class 0 (duplicate box)
    val_box_content = (
        "0 0.5 0.5 0.2 0.2\n0 1.2 0.5 0.2 0.2\n0 0.5 0.5 0.001 0.001\n0 0.5 0.5 0.2 0.2\n"
    )
    (val_labels / "img1.txt").write_text(val_box_content, encoding="utf-8")

    # Empty annotation file for img2
    (train_labels / "img2.txt").write_text("", encoding="utf-8")

    # data.yaml
    (tmp_path / "data.yaml").write_text("names: ['object']\n", encoding="utf-8")

    out = _run_inspect(DatasetInspectInput(dataset_path=tmp_path))

    # Assertions on quality intelligence
    assert out.quality_score < 100.0
    assert out.label_anomalies.out_of_bounds == 1
    assert out.label_anomalies.tiny_boxes == 1
    assert out.label_anomalies.empty_labels == 1
    assert out.label_anomalies.suspiciously_overlapping == 1
    assert out.duplicate_groups_count == 1
    assert out.total_duplicates_found == 2
    assert len(out.leaked_images) == 1
    normalized_leak_path = out.leaked_images[0].train_image.replace("\\", "/")
    assert normalized_leak_path == "images/train/img1.jpg"

    # Confirm auto fix items
    actions = [item.action for item in out.auto_fix_plan]
    assert "Remove duplicate images" in actions
    assert "Remove train-val/test leakage" in actions
    assert "Clip out-of-bounds bounding boxes" in actions
    assert "Filter tiny bounding boxes" in actions
    assert "Merge overlapping bounding boxes" in actions

    # Confirm dataset card contains details
    assert "# Dataset Card" in out.dataset_card
    assert "Quality Score" in out.dataset_card
    assert "Tiny Boxes:" in out.dataset_card

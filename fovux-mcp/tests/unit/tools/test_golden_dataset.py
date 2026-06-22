"""Unit tests for dataset inspection and validation using a golden dataset."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from fovux.schemas.dataset import DatasetInspectInput, DatasetValidateInput
from fovux.tools.dataset_inspect import _run_inspect
from fovux.tools.dataset_validate import _run_validate


def _create_unique_image(path: Path, seed: int) -> None:
    """Create visually distinct images so their phash values differ."""
    img = Image.new(
        "RGB",
        (64, 64),
        color=(seed * 37 % 256, seed * 73 % 256, seed * 109 % 256),
    )
    draw = ImageDraw.Draw(img)
    draw.line(
        (0, seed * 13 % 64, 64, (64 - seed * 17) % 64),
        fill=(255, 255, 0),
        width=3,
    )
    draw.rectangle(
        [seed * 7 % 30, seed * 11 % 30, 40, 40],
        outline=(0, 255, 255),
        width=2,
    )
    img.save(path)


@pytest.fixture()
def golden_dataset_path(tmp_path: Path) -> Path:
    """Create a golden dataset with multiple edge cases.

    Edge cases included:
      - Unicode folder names & filenames (e.g. türkçe)
      - Corrupt images (junk/empty files)
      - Missing labels (image exists, no label file)
      - Train/val leakage (same image in both train and val splits)
      - Class mismatch (nc is 2, but names has 1 item; class ID 2 in label is out of range)
      - Windows path slashes (train path uses backslashes in data.yaml)
    """
    # Create a Unicode named dataset root
    ds_root = tmp_path / "türkçe_dataset"
    ds_root.mkdir()

    # Create directories for train and val splits
    (ds_root / "images" / "train").mkdir(parents=True)
    (ds_root / "images" / "val").mkdir(parents=True)
    (ds_root / "labels" / "train").mkdir(parents=True)
    (ds_root / "labels" / "val").mkdir(parents=True)

    # 1. Windows path slashes inside data.yaml + class mismatch
    # nc: 2, but names only has 1 item
    yaml_content = "path: .\ntrain: images\\train\nval: images/val\nnc: 2\nnames:\n  0: cat\n"
    (ds_root / "data.yaml").write_text(yaml_content, encoding="utf-8")

    # 2. Unicode filename & class ID out of range
    # label contains class 0 (valid) and class 2 (out of range since nc is 2)
    img_unicode = ds_root / "images" / "train" / "türkçe_resim.jpg"
    lbl_unicode = ds_root / "labels" / "train" / "türkçe_resim.txt"
    _create_unique_image(img_unicode, seed=1)
    lbl_unicode.write_text("0 0.5 0.5 0.2 0.2\n2 0.5 0.5 0.2 0.2\n", encoding="utf-8")

    # 3. Corrupt image (unreadable)
    img_corrupt = ds_root / "images" / "train" / "corrupt.jpg"
    img_corrupt.write_bytes(b"invalid-image-data-corrupt")
    (ds_root / "labels" / "train" / "corrupt.txt").write_text(
        "0 0.5 0.5 0.2 0.2\n", encoding="utf-8"
    )

    # 4. Missing labels (image exists, no label file)
    img_missing = ds_root / "images" / "train" / "missing_label.jpg"
    _create_unique_image(img_missing, seed=2)

    # 5. Train/val split leakage
    # We write identical images to train and val
    leak_train_path = ds_root / "images" / "train" / "leak.jpg"
    leak_val_path = ds_root / "images" / "val" / "leak.jpg"
    _create_unique_image(leak_train_path, seed=3)
    # Copy file to val split to ensure exactly identical contents & phash
    leak_val_path.write_bytes(leak_train_path.read_bytes())

    (ds_root / "labels" / "train" / "leak.txt").write_text("0 0.5 0.5 0.3 0.3\n", encoding="utf-8")
    (ds_root / "labels" / "val" / "leak.txt").write_text("0 0.5 0.5 0.3 0.3\n", encoding="utf-8")

    return ds_root


def test_golden_dataset_validation(golden_dataset_path: Path) -> None:
    """Ensure dataset validation detects the expected edge cases."""
    inp = DatasetValidateInput(
        dataset_path=golden_dataset_path,
        check_image_readable=True,
        check_bbox_bounds=True,
        check_class_id_range=True,
        strict=False,
    )
    out = _run_validate(inp)

    # It must fail because of the corrupt image or class ID range issues
    assert out.valid is False
    all_issues = out.errors + out.warnings

    # Validate that we found class ID range issues
    assert any("class id 2 out of range" in i.message.lower() for i in all_issues)

    # Validate that we found unreadable/corrupt image issues
    assert any("image unreadable" in i.message.lower() for i in all_issues)

    # Validate that we flagged the missing label file for missing_label.jpg
    assert any(
        "image has no corresponding label file" in i.message.lower()
        and "missing_label.jpg" in i.file
        for i in all_issues
    )


def test_golden_dataset_inspection(golden_dataset_path: Path) -> None:
    """Ensure dataset inspection detects split leakage, duplicates, and corrupt files."""
    inp = DatasetInspectInput(
        dataset_path=golden_dataset_path,
        format="yolo",
        include_samples=True,
    )
    out = _run_inspect(inp)

    assert out.format_detected == "yolo"
    # Total images should be: türkçe_resim, corrupt, missing_label, leak (train), leak (val) = 5
    assert out.total_images == 5

    # Check that the unreadable/corrupt image was detected
    assert out.label_anomalies.empty_labels == 0
    assert any("cannot read image" in w.lower() for w in out.warnings)

    # Check for missing label image
    assert len(out.missing_label_images) == 1
    assert out.missing_label_images[0].name == "missing_label.jpg"

    # Check train/val split leakage
    assert len(out.leaked_images) == 1
    assert "leak.jpg" in out.leaked_images[0].train_image
    assert "leak.jpg" in out.leaked_images[0].val_image

    # Check quality score is degraded appropriately due to anomalies and leakage
    assert out.quality_score < 100.0
    assert "Remove train-val/test leakage" in [item.action for item in out.auto_fix_plan]

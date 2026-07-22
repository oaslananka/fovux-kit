"""Golden COCO coverage for the normalized inspect/validate boundary."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from fovux.schemas.dataset import DatasetInspectInput, DatasetValidateInput
from fovux.tools.dataset_inspect import _run_inspect
from fovux.tools.dataset_validate import _run_validate


def _unique_image(path: Path, seed: int) -> None:
    image = Image.new("RGB", (80, 60), color=(seed * 41 % 255, seed * 71 % 255, 90))
    draw = ImageDraw.Draw(image)
    draw.line((0, seed * 9 % 60, 79, seed * 17 % 60), fill=(255, 255, 0), width=3)
    image.save(path)


def test_golden_coco_covers_corrupt_duplicate_leakage_unicode_and_class_mismatch(
    tmp_path: Path,
) -> None:
    root = tmp_path / "görüntü_dataset"
    images = root / "images"
    annotations = root / "annotations"
    images.mkdir(parents=True)
    annotations.mkdir()

    unicode_image = images / "türkçe.jpg"
    corrupt_image = images / "corrupt.jpg"
    train_leak = images / "train_leak.jpg"
    val_leak = images / "val_leak.jpg"
    _unique_image(unicode_image, 1)
    corrupt_image.write_bytes(b"not-an-image")
    _unique_image(train_leak, 2)
    val_leak.write_bytes(train_leak.read_bytes())

    train_payload = {
        "images": [
            {"id": 1, "file_name": unicode_image.name, "width": 80, "height": 60},
            {"id": 2, "file_name": corrupt_image.name, "width": 80, "height": 60},
            {"id": 3, "file_name": train_leak.name, "width": 80, "height": 60},
        ],
        "categories": [{"id": 1, "name": "nesne"}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 2, "bbox": [-5, 0, 90, 60]},
            {"id": 2, "image_id": 2, "category_id": 1, "bbox": [10, 10, 20, 20]},
            {"id": 3, "image_id": 3, "category_id": 1, "bbox": [10, 10, 20, 20]},
        ],
    }
    val_payload = {
        "images": [{"id": 4, "file_name": val_leak.name, "width": 80, "height": 60}],
        "categories": [{"id": 1, "name": "nesne"}],
        "annotations": [{"id": 4, "image_id": 4, "category_id": 1, "bbox": [10, 10, 20, 20]}],
    }
    (annotations / "instances_train.json").write_text(
        json.dumps(train_payload, ensure_ascii=False), encoding="utf-8"
    )
    (annotations / "instances_val.json").write_text(
        json.dumps(val_payload, ensure_ascii=False), encoding="utf-8"
    )

    inspection = _run_inspect(DatasetInspectInput(dataset_path=root, format="coco"))
    validation = _run_validate(DatasetValidateInput(dataset_path=root, format="coco"))

    assert inspection.total_images == 4
    assert inspection.duplicate_groups_count == 1
    assert inspection.total_duplicates_found == 2
    assert len(inspection.leaked_images) == 1
    assert inspection.leaked_images[0].train_image.endswith("train_leak.jpg")
    assert inspection.leaked_images[0].val_image is not None
    assert inspection.leaked_images[0].val_image.endswith("val_leak.jpg")
    assert any("corrupt.jpg" in warning for warning in inspection.warnings)
    assert any(path.name == "türkçe.jpg" for path in inspection.sample_paths)

    assert validation.valid is False
    issues = validation.errors + validation.warnings
    assert any("class id 2" in issue.message.lower() for issue in issues)
    assert any("bbox out of [0,1] range" in issue.message.lower() for issue in issues)
    assert any("image unreadable" in issue.message.lower() for issue in issues)

"""Tests for the normalized dataset inventory and format adapters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from fovux.core.dataset_inventory import (
    DatasetInventory,
    build_dataset_inventory,
    registered_dataset_formats,
)
from fovux.core.errors import FovuxDatasetFormatError, FovuxPathValidationError

FIXTURES = Path(__file__).parents[2] / "fixtures"


def test_yolo_and_coco_adapters_produce_the_same_inventory_contract() -> None:
    yolo = build_dataset_inventory(FIXTURES / "mini_yolo", "yolo", analyze_images=False)
    coco = build_dataset_inventory(FIXTURES / "mini_coco", "coco", analyze_images=False)

    for inventory in (yolo, coco):
        assert isinstance(inventory, DatasetInventory)
        assert inventory.root.is_absolute()
        assert inventory.images
        assert inventory.annotations
        assert inventory.class_names
        assert sum(inventory.splits.values()) == len(inventory.images)
        assert all(record.image_id for record in inventory.images)
        assert all(annotation.source_path.is_absolute() for annotation in inventory.annotations)
        assert all(annotation.bbox is not None for annotation in inventory.annotations)
        assert all(
            annotation.bbox.area_ratio >= 0.0
            for annotation in inventory.annotations
            if annotation.bbox
        )

    assert yolo.format == "yolo"
    assert len(yolo.images) == 40
    assert len(yolo.annotations) == 40
    assert list(yolo.class_names.values()) == ["cat", "dog"]

    assert coco.format == "coco"
    assert len(coco.images) == 20
    assert list(coco.class_names.values()) == ["cat", "dog"]


def test_inventory_exposes_shared_class_and_annotation_statistics() -> None:
    inventory = build_dataset_inventory(
        FIXTURES / "mini_yolo",
        "yolo",
        analyze_images=False,
    )

    assert inventory.class_counts == {0: 20, 1: 20}
    assert inventory.annotation_counts_per_image
    assert sum(inventory.annotation_counts_per_image) == len(inventory.annotations)
    assert all(area > 0 for area in inventory.bbox_area_ratios)
    assert inventory.missing_annotation_images == []
    assert inventory.orphan_annotation_sources == []


def test_coco_adapter_normalizes_pixel_boxes_to_image_relative_coordinates(tmp_path: Path) -> None:
    images = tmp_path / "images"
    annotations = tmp_path / "annotations"
    images.mkdir()
    annotations.mkdir()
    Image.new("RGB", (200, 100), color=(20, 30, 40)).save(images / "örnek.jpg")
    payload = {
        "images": [{"id": 7, "file_name": "örnek.jpg", "width": 200, "height": 100}],
        "categories": [{"id": 3, "name": "nesne"}],
        "annotations": [{"id": 11, "image_id": 7, "category_id": 3, "bbox": [20, 10, 80, 40]}],
    }
    (annotations / "instances_train.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    inventory = build_dataset_inventory(tmp_path, "coco", analyze_images=False)

    annotation = inventory.annotations[0]
    assert annotation.bbox is not None
    assert annotation.bbox.x_min == pytest.approx(0.1)
    assert annotation.bbox.y_min == pytest.approx(0.1)
    assert annotation.bbox.x_max == pytest.approx(0.5)
    assert annotation.bbox.y_max == pytest.approx(0.5)
    assert annotation.bbox.area_ratio == pytest.approx(0.16)
    assert inventory.images[0].path.name == "örnek.jpg"


def test_inventory_registry_is_explicit_and_rejects_unsupported_formats(tmp_path: Path) -> None:
    assert registered_dataset_formats() == ("coco", "yolo")

    with pytest.raises(FovuxDatasetFormatError, match="normalized inventory"):
        build_dataset_inventory(tmp_path, "voc", analyze_images=False)


def test_coco_adapter_rejects_image_paths_that_escape_dataset_root(tmp_path: Path) -> None:
    annotations = tmp_path / "annotations"
    annotations.mkdir()
    outside_image = tmp_path.parent / "outside.jpg"
    Image.new("RGB", (16, 16), color=(1, 2, 3)).save(outside_image)
    payload = {
        "images": [
            {
                "id": 1,
                "file_name": f"../{outside_image.name}",
                "width": 16,
                "height": 16,
            }
        ],
        "categories": [{"id": 1, "name": "object"}],
        "annotations": [],
    }
    (annotations / "instances_train.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(FovuxPathValidationError, match="escapes allowed root"):
        build_dataset_inventory(tmp_path, "coco", analyze_images=False)

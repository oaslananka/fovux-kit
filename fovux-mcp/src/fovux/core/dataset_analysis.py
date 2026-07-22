"""Shared statistics and quality findings for normalized dataset inventories."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from fovux.core.dataset_inventory import (
    AnnotationRecord,
    DatasetInventory,
    ImageRecord,
    NormalizedBoundingBox,
)


@dataclass(frozen=True, slots=True)
class InventoryLeakage:
    """A duplicate image crossing train/validation/test boundaries."""

    train_image: Path
    val_image: Path | None = None
    test_image: Path | None = None


@dataclass(frozen=True, slots=True)
class InventoryAnalysis:
    """Format-neutral statistics derived once from an inventory."""

    class_ids: list[int]
    class_counts: dict[int, int]
    annotation_counts: list[int]
    normalized_bbox_areas: list[float]
    raw_bbox_areas: list[float]
    image_widths: list[float]
    unreadable_count: int
    tiny_count: int
    out_of_bounds_count: int
    empty_annotation_count: int
    overlapping_count: int
    duplicate_groups: list[list[Path]]
    leakage: list[InventoryLeakage]


def analyze_dataset_inventory(
    inventory: DatasetInventory,
    *,
    duplicate_hamming_threshold: int = 5,
) -> InventoryAnalysis:
    """Compute shared class, box, duplicate, leakage, and anomaly statistics."""
    class_counts = inventory.class_counts
    class_ids = sorted(set(class_counts) | set(inventory.class_names))
    annotations_by_image: dict[str, list[AnnotationRecord]] = defaultdict(list)
    for annotation in inventory.annotations:
        annotations_by_image[annotation.image_id].append(annotation)

    normalized_areas = [
        annotation.bbox.area_ratio
        for annotation in inventory.annotations
        if annotation.bbox is not None
    ]
    raw_areas = [annotation.raw_area for annotation in inventory.annotations]
    unreadable_count = sum(image.readable is False for image in inventory.images)
    tiny_count = sum(area < 0.0005 for area in normalized_areas)
    out_of_bounds_count = sum(
        annotation.bbox is not None and not annotation.bbox.is_within_bounds
        for annotation in inventory.annotations
    )
    empty_annotation_count = sum(
        not annotations_by_image[image.image_id]
        and (inventory.format == "coco" or image.annotation_source_exists)
        for image in inventory.images
    )
    overlapping_count = sum(
        _count_overlapping_annotations(annotations_by_image[image.image_id])
        for image in inventory.images
    )
    duplicate_groups = _find_duplicate_groups(
        inventory.images,
        hamming_threshold=duplicate_hamming_threshold,
    )
    return InventoryAnalysis(
        class_ids=class_ids,
        class_counts=class_counts,
        annotation_counts=[len(annotations_by_image[image.image_id]) for image in inventory.images],
        normalized_bbox_areas=normalized_areas,
        raw_bbox_areas=raw_areas,
        image_widths=[
            float(image.width)
            for image in inventory.images
            if image.analyzed and image.width is not None
        ],
        unreadable_count=unreadable_count,
        tiny_count=tiny_count,
        out_of_bounds_count=out_of_bounds_count,
        empty_annotation_count=empty_annotation_count,
        overlapping_count=overlapping_count,
        duplicate_groups=duplicate_groups,
        leakage=_find_leakage(inventory, duplicate_groups),
    )


def _count_overlapping_annotations(annotations: list[AnnotationRecord]) -> int:
    count = 0
    for index, first in enumerate(annotations):
        if first.bbox is None:
            continue
        for second in annotations[index + 1 :]:
            if second.bbox is None or first.class_id != second.class_id:
                continue
            if _normalized_iou(first.bbox, second.bbox) > 0.90:
                count += 1
    return count


def _normalized_iou(first: NormalizedBoundingBox, second: NormalizedBoundingBox) -> float:
    intersection_width = max(0.0, min(first.x_max, second.x_max) - max(first.x_min, second.x_min))
    intersection_height = max(
        0.0,
        min(first.y_max, second.y_max) - max(first.y_min, second.y_min),
    )
    intersection = intersection_width * intersection_height
    union = first.area_ratio + second.area_ratio - intersection
    return intersection / union if union > 0 else 0.0


def _find_duplicate_groups(
    images: list[ImageRecord],
    *,
    hamming_threshold: int,
) -> list[list[Path]]:
    hashed = [(image.path, image.fingerprint) for image in images if image.fingerprint]
    groups: list[list[Path]] = []
    used_indices: set[int] = set()
    for index, (first_path, first_hash) in enumerate(hashed):
        if index in used_indices or first_hash is None:
            continue
        group = [first_path]
        for candidate_index in range(index + 1, len(hashed)):
            if candidate_index in used_indices:
                continue
            candidate_path, candidate_hash = hashed[candidate_index]
            if candidate_hash is None:
                continue
            if _hash_distance(first_hash, candidate_hash) <= hamming_threshold:
                group.append(candidate_path)
                used_indices.add(candidate_index)
        if len(group) > 1:
            used_indices.add(index)
            groups.append(group)
    return groups


def _hash_distance(first: str, second: str) -> int:
    try:
        return (int(first, 16) ^ int(second, 16)).bit_count()
    except ValueError:
        return max(len(first), len(second))


def _find_leakage(
    inventory: DatasetInventory,
    duplicate_groups: list[list[Path]],
) -> list[InventoryLeakage]:
    split_by_path = {image.path: image.split for image in inventory.images}
    issues: list[InventoryLeakage] = []
    for group in duplicate_groups:
        by_split: dict[str, list[Path]] = defaultdict(list)
        for path in group:
            by_split[split_by_path.get(path, "unknown")].append(path)
        if len(by_split) <= 1:
            continue
        train_images = by_split.get("train", []) or [group[0]]
        for train_image in train_images:
            issues.extend(
                InventoryLeakage(train_image=train_image, val_image=val_image)
                for val_image in by_split.get("val", [])
            )
            issues.extend(
                InventoryLeakage(train_image=train_image, test_image=test_image)
                for test_image in by_split.get("test", [])
            )
    return issues

"""Shared utilities for dataset tools: format detection, label reading, image finding."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}


def find_images(root: Path, max_count: int | None = None) -> list[Path]:
    """Recursively find all image files under root.

    Args:
        root: Directory to search.
        max_count: Stop after this many images (None = no limit).

    Returns:
        Sorted list of image Paths.
    """
    root = root.resolve(strict=False)
    if root == root.parent:
        return []

    images: list[Path] = []
    for p in root.rglob("*"):
        if p.suffix.lower() in IMAGE_EXTENSIONS and p.is_file():
            images.append(p)
            if max_count and len(images) >= max_count:
                break
    return sorted(images)


def detect_format(dataset_path: Path) -> str:
    """Auto-detect dataset format.

    Args:
        dataset_path: Root directory of the dataset.

    Returns:
        One of 'yolo', 'coco', 'voc', or raises FovuxDatasetFormatError.
    """
    from fovux.core.errors import FovuxDatasetFormatError

    if (dataset_path / "data.yaml").exists() or (dataset_path / "dataset.yaml").exists():
        return "yolo"

    ann_dir = dataset_path / "annotations"
    if ann_dir.is_dir():
        json_files = list(ann_dir.glob("*.json"))
        if json_files:
            try:
                with json_files[0].open() as f:
                    data = json.load(f)
                if "annotations" in data and "categories" in data:
                    return "coco"
            except (json.JSONDecodeError, KeyError):
                pass

    if _has_voc_annotations(dataset_path):
        return "voc"

    raise FovuxDatasetFormatError(
        f"Cannot detect dataset format in {dataset_path}. "
        "Expected data.yaml (YOLO), annotations/*.json (COCO), or Annotations/*.xml (VOC).",
        hint="Specify format explicitly with format='yolo'|'coco'|'voc'.",
    )


def _has_voc_annotations(dataset_path: Path) -> bool:
    """Return true when standard VOC annotation files are present.

    VOC detection intentionally checks only conventional shallow locations. A
    broad recursive search can traverse an entire drive when adversarial input
    points at a filesystem root.
    """
    for annotations_dir in (
        dataset_path / "Annotations",
        dataset_path / "annotations",
    ):
        if annotations_dir.is_dir() and next(annotations_dir.glob("*.xml"), None) is not None:
            return True
    return next(dataset_path.glob("*.xml"), None) is not None


# ── YOLO helpers ──────────────────────────────────────────────────────────────


def read_yolo_data_yaml(dataset_path: Path) -> dict[str, Any]:
    """Read and parse data.yaml for a YOLO dataset.

    Args:
        dataset_path: Root directory containing data.yaml.

    Returns:
        Parsed YAML dict.
    """
    from fovux.core.dataset_config import validate_yolo_data_yaml

    return validate_yolo_data_yaml(dataset_path)


def iter_yolo_labels(dataset_path: Path, split: str | None = None) -> Iterator[tuple[Path, Path]]:
    """Yield (image_path, label_path) pairs for a YOLO dataset.

    Args:
        dataset_path: Root directory.
        split: 'train' | 'val' | 'test' | None (all splits).

    Yields:
        Tuples of (image_path, label_path).
    """
    labels_root = dataset_path / "labels"
    images_root = dataset_path / "images"

    if not labels_root.is_dir():
        return

    splits = [split] if split else [d.name for d in labels_root.iterdir() if d.is_dir()]
    if not splits:
        splits = [""]

    for s in splits:
        ldir = labels_root / s if s else labels_root
        idir = images_root / s if s else images_root
        if not ldir.is_dir():
            continue
        for label_file in sorted(ldir.glob("*.txt")):
            stem = label_file.stem
            img = None
            for ext in IMAGE_EXTENSIONS:
                candidate = idir / (stem + ext)
                if candidate.exists():
                    img = candidate
                    break
            if img is None:
                img = idir / (stem + ".jpg")
            yield img, label_file


def parse_yolo_label(label_path: Path) -> list[tuple[int, float, float, float, float]]:
    """Parse a YOLO label file into a list of (class_id, cx, cy, w, h).

    Args:
        label_path: Path to the .txt label file.

    Returns:
        List of annotation tuples. Empty if file is empty.
    """
    annotations: list[tuple[int, float, float, float, float]] = []
    if not label_path.exists():
        return annotations
    with label_path.open() as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            try:
                cls = int(parts[0])
                cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                annotations.append((cls, cx, cy, w, h))
            except ValueError:
                continue
    return annotations


# ── COCO helpers ──────────────────────────────────────────────────────────────


def read_coco_json(json_path: Path) -> dict[str, Any]:
    """Read and return a COCO annotation JSON.

    Args:
        json_path: Path to the COCO JSON file.

    Returns:
        Parsed COCO dict.
    """
    with json_path.open() as f:
        return cast(dict[str, Any], json.load(f))


def find_coco_jsons(dataset_path: Path) -> list[Path]:
    """Find all COCO annotation JSON files.

    Args:
        dataset_path: Root directory.

    Returns:
        List of JSON paths.
    """
    ann_dir = dataset_path / "annotations"
    if ann_dir.is_dir():
        return sorted(ann_dir.glob("*.json"))
    return []


# ── Gini coefficient ──────────────────────────────────────────────────────────


def gini(counts: list[int]) -> float:
    """Compute Gini coefficient for class imbalance.

    0 = perfectly balanced, 1 = all samples in one class.

    Args:
        counts: List of sample counts per class.

    Returns:
        Gini coefficient as a float in [0, 1].
    """
    if not counts or sum(counts) == 0:
        return 0.0
    n = len(counts)
    if n == 1:
        return 0.0
    s = sorted(counts)
    total = sum(s)
    gini_num = sum((i + 1) * v for i, v in enumerate(s))
    return float(1 - (2 * gini_num) / (n * total))


def bucket_distribution(values: list[float], n_buckets: int = 10) -> tuple[list[str], list[int]]:
    """Create a histogram from a list of float values.

    Args:
        values: Input values.
        n_buckets: Number of histogram buckets.

    Returns:
        Tuple of (bucket_labels, counts).
    """
    if not values:
        return [], []
    mn, mx = min(values), max(values)
    if mn == mx:
        return [str(round(mn, 2))], [len(values)]
    step = (mx - mn) / n_buckets
    buckets = [mn + i * step for i in range(n_buckets + 1)]
    counts = [0] * n_buckets
    labels = []
    for i in range(n_buckets):
        labels.append(f"{buckets[i]:.1f}-{buckets[i + 1]:.1f}")
    for v in values:
        idx = min(int((v - mn) / step), n_buckets - 1)
        counts[idx] += 1
    return labels, counts

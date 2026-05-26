"""dataset_inspect — comprehensive dataset statistics tool."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fovux.core.dataset_utils import (
    bucket_distribution,
    detect_format,
    find_coco_jsons,
    gini,
    parse_yolo_label,
    read_coco_json,
    read_yolo_data_yaml,
)
from fovux.core.errors import (
    FovuxDatasetEmptyError,
    FovuxDatasetFormatError,
    FovuxDatasetNotFoundError,
)
from fovux.core.tooling import tool_event
from fovux.core.validation import ensure_within_root, resolve_local_path, validate_file_size
from fovux.schemas.dataset import (
    ClassStat,
    DatasetInspectInput,
    DatasetInspectOutput,
    Histogram,
    SizeHistogram,
)
from fovux.server import mcp

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@mcp.tool()
def dataset_inspect(
    dataset_path: str,
    format: str = "auto",
    include_samples: bool = True,
    max_images_analyzed: int = 10_000,
) -> dict[str, Any]:
    """Produce comprehensive statistics for a dataset: classes, bbox distributions, splits, orphans.

    Supports YOLO, COCO, VOC (auto-detected). Returns class balance, Gini coefficient, and warnings.
    """
    inp = DatasetInspectInput(
        dataset_path=Path(dataset_path),
        format=format,  # type: ignore[arg-type]
        include_samples=include_samples,
        max_images_analyzed=max_images_analyzed,
    )
    with tool_event(
        "dataset_inspect",
        dataset_path=dataset_path,
        format=format,
        include_samples=include_samples,
    ):
        return _run_inspect(inp).model_dump(mode="json")


def _run_inspect(inp: DatasetInspectInput) -> DatasetInspectOutput:
    t0 = time.perf_counter()
    path = resolve_local_path(inp.dataset_path)

    if not path.exists():
        raise FovuxDatasetNotFoundError(str(path))

    fmt = inp.format if inp.format != "auto" else detect_format(path)

    if fmt == "yolo":
        return _inspect_yolo(path, inp, fmt, t0)
    if fmt == "coco":
        return _inspect_coco(path, inp, fmt, t0)
    raise FovuxDatasetFormatError(
        (f"dataset_inspect currently supports YOLO and COCO datasets only; received '{fmt}'."),
        hint="Convert the dataset to YOLO or COCO before inspection.",
    )


def _inspect_yolo(
    path: Path, inp: DatasetInspectInput, fmt: str, t0: float
) -> DatasetInspectOutput:
    warnings: list[str] = []

    try:
        meta = read_yolo_data_yaml(path)
        class_names: list[str] = meta.get("names", [])
        if isinstance(class_names, dict):
            class_names = list(class_names.values())
    except Exception:
        class_names = []
        warnings.append("Could not parse data.yaml — class names unknown.")

    images_dir = path / "images"
    splits_detected: dict[str, int] = {}
    if images_dir.is_dir():
        for subdir in sorted(images_dir.iterdir()):
            if subdir.is_dir():
                cnt = sum(1 for f in subdir.rglob("*") if f.suffix.lower() in _IMAGE_EXTS)
                if cnt:
                    splits_detected[subdir.name] = cnt

    class_counts: dict[int, int] = {}
    bbox_areas: list[float] = []
    bbox_counts_per_image: list[int] = []
    orphan_images = 0
    orphan_annotations = 0
    missing_label_images: list[Path] = []
    image_sizes: list[tuple[int, int]] = []
    sample_paths: list[Path] = []
    total_images = 0
    total_annotations = 0
    labels_dir = path / "labels"
    image_paths = _discover_yolo_images(path)[: inp.max_images_analyzed]

    if labels_dir.is_dir():
        for label_path in sorted(labels_dir.rglob("*.txt")):
            if not _matching_yolo_image_exists(path, label_path):
                orphan_annotations += 1

    for img_path in image_paths:
        label_path = _label_path_for_image(path, img_path)
        total_images += 1

        img_exists = True
        label_exists = label_path.exists()

        if img_exists and not label_exists:
            orphan_images += 1
            missing_label_images.append(img_path)

        if img_exists and len(sample_paths) < 10 and inp.include_samples:
            sample_paths.append(img_path)

        if img_exists:
            try:
                from PIL import Image

                safe_img_path = ensure_within_root(img_path, path)
                validate_file_size(safe_img_path)
                with Image.open(safe_img_path) as im:
                    image_sizes.append(im.size)
            except Exception:
                warnings.append(f"Cannot read image: {img_path.name}")

        anns = parse_yolo_label(label_path) if label_exists else []
        bbox_counts_per_image.append(len(anns))
        total_annotations += len(anns)
        for cls, _, _, w, h in anns:
            class_counts[cls] = class_counts.get(cls, 0) + 1
            bbox_areas.append(w * h)

    if total_images == 0:
        raise FovuxDatasetEmptyError(str(path))

    total_anns = sum(class_counts.values()) or 1
    classes = [
        ClassStat(
            name=class_names[idx] if idx < len(class_names) else f"class_{idx}",
            count=cnt,
            pct=round(cnt / total_anns * 100, 2),
        )
        for idx, cnt in sorted(class_counts.items())
    ]

    wl, wc = bucket_distribution([float(s[0]) for s in image_sizes])
    img_size_hist = SizeHistogram(buckets=wl or ["N/A"], counts=wc or [0])
    bal, bac = bucket_distribution([a * 100 for a in bbox_areas])
    bbox_size_hist = SizeHistogram(buckets=bal or ["N/A"], counts=bac or [0])
    bcl, bcc = bucket_distribution([float(c) for c in bbox_counts_per_image])
    bbox_count_hist = Histogram(buckets=bcl or ["0"], counts=bcc or [total_images])

    return DatasetInspectOutput(
        format_detected=fmt,
        total_images=total_images,
        total_annotations=total_annotations,
        num_classes=len(class_counts),
        classes=classes,
        image_size_distribution=img_size_hist,
        bbox_size_distribution=bbox_size_hist,
        bbox_size_buckets=_normalized_bbox_size_buckets(bbox_areas),
        bbox_count_per_image=bbox_count_hist,
        orphan_images=orphan_images,
        missing_label_images=missing_label_images,
        orphan_annotations=orphan_annotations,
        class_balance_gini=gini(list(class_counts.values())),
        splits_detected=splits_detected,
        warnings=warnings,
        sample_paths=sample_paths,
        analysis_duration_seconds=round(time.perf_counter() - t0, 3),
    )


def _inspect_coco(
    path: Path, inp: DatasetInspectInput, fmt: str, t0: float
) -> DatasetInspectOutput:
    warnings: list[str] = []
    json_files = find_coco_jsons(path)
    if not json_files:
        raise FovuxDatasetEmptyError(str(path))

    class_counts: dict[int, int] = {}
    id_to_name: dict[int, str] = {}
    total_images = 0
    total_annotations = 0
    splits_detected: dict[str, int] = {}
    bbox_areas: list[float] = []
    bbox_per_img: dict[int, int] = {}
    sample_paths: list[Path] = []

    for jf in json_files:
        try:
            data = read_coco_json(jf)
        except Exception as e:
            warnings.append(f"Cannot parse {jf.name}: {e}")
            continue

        for cat in data.get("categories", []):
            id_to_name[cat["id"]] = cat["name"]

        imgs = data.get("images", [])
        total_images += len(imgs)
        split_name = jf.stem.split("_")[-1] if "_" in jf.stem else jf.stem
        splits_detected[split_name] = len(imgs)

        images_dir = path / "images"
        for img_info in imgs[:10]:
            p = images_dir / img_info.get("file_name", "")
            if p.exists() and len(sample_paths) < 10:
                sample_paths.append(p)

        for ann in data.get("annotations", []):
            total_annotations += 1
            cat_id = ann.get("category_id", 0)
            class_counts[cat_id] = class_counts.get(cat_id, 0) + 1
            img_id = ann.get("image_id", 0)
            bbox_per_img[img_id] = bbox_per_img.get(img_id, 0) + 1
            bbox = ann.get("bbox", [0, 0, 1, 1])
            if len(bbox) >= 4:
                bbox_areas.append(float(bbox[2] * bbox[3]))

    if total_images == 0:
        raise FovuxDatasetEmptyError(str(path))

    total_anns = sum(class_counts.values()) or 1
    classes = [
        ClassStat(
            name=id_to_name.get(cid, f"class_{cid}"),
            count=cnt,
            pct=round(cnt / total_anns * 100, 2),
        )
        for cid, cnt in sorted(class_counts.items())
    ]

    bal, bac = bucket_distribution(bbox_areas)
    bcl, bcc = bucket_distribution([float(v) for v in bbox_per_img.values()])

    return DatasetInspectOutput(
        format_detected=fmt,
        total_images=total_images,
        total_annotations=total_annotations,
        num_classes=len(class_counts),
        classes=classes,
        image_size_distribution=SizeHistogram(buckets=["N/A"], counts=[total_images]),
        bbox_size_distribution=SizeHistogram(buckets=bal or ["N/A"], counts=bac or [0]),
        bbox_size_buckets={},
        bbox_count_per_image=Histogram(buckets=bcl or ["0"], counts=bcc or [0]),
        orphan_images=0,
        missing_label_images=[],
        orphan_annotations=0,
        class_balance_gini=gini(list(class_counts.values())),
        splits_detected=splits_detected,
        warnings=warnings,
        sample_paths=sample_paths,
        analysis_duration_seconds=round(time.perf_counter() - t0, 3),
    )


def _discover_yolo_images(dataset_path: Path) -> list[Path]:
    images_root = dataset_path / "images"
    if not images_root.is_dir():
        return []
    return sorted(path for path in images_root.rglob("*") if path.suffix.lower() in _IMAGE_EXTS)


def _label_path_for_image(dataset_path: Path, image_path: Path) -> Path:
    images_root = dataset_path / "images"
    labels_root = dataset_path / "labels"
    try:
        relative = image_path.relative_to(images_root)
    except ValueError:
        relative = Path(image_path.name)
    return labels_root / relative.with_suffix(".txt")


def _matching_yolo_image_exists(dataset_path: Path, label_path: Path) -> bool:
    labels_root = dataset_path / "labels"
    images_root = dataset_path / "images"
    try:
        relative = label_path.relative_to(labels_root).with_suffix("")
    except ValueError:
        relative = Path(label_path.stem)
    return any((images_root / relative).with_suffix(ext).exists() for ext in _IMAGE_EXTS)


def _normalized_bbox_size_buckets(areas: list[float]) -> dict[str, int]:
    buckets = {"small": 0, "medium": 0, "large": 0}
    for area in areas:
        if area < 0.01:
            buckets["small"] += 1
        elif area < 0.10:
            buckets["medium"] += 1
        else:
            buckets["large"] += 1
    return buckets

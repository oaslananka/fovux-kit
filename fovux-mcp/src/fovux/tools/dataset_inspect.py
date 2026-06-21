"""dataset_inspect — comprehensive dataset statistics and quality intelligence tool."""

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
    AutoFixItem,
    ClassStat,
    DatasetInspectInput,
    DatasetInspectOutput,
    Histogram,
    LabelAnomalySummary,
    LeakageIssue,
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
    """Produce comprehensive statistics and quality metrics for a dataset.

    Returns Gini coefficient, Gini-based quality score, label anomaly audits,
    leakage/duplicate reports, and suggested auto-fix plan actions.
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


def _calculate_iou(
    box1: tuple[float, float, float, float], box2: tuple[float, float, float, float]
) -> float:
    cx1, cy1, w1, h1 = box1
    cx2, cy2, w2, h2 = box2
    x1_1, y1_1, x2_1, y2_1 = cx1 - w1 / 2, cy1 - h1 / 2, cx1 + w1 / 2, cy1 + h1 / 2
    x1_2, y1_2, x2_2, y2_2 = cx2 - w2 / 2, cy2 - h2 / 2, cx2 + w2 / 2, cy2 + h2 / 2
    inter_x1 = max(x1_1, x1_2)
    inter_y1 = max(y1_1, y1_2)
    inter_x2 = min(x2_1, x2_2)
    inter_y2 = min(y2_1, y2_2)
    if inter_x1 < inter_x2 and inter_y1 < inter_y2:
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    else:
        inter_area = 0.0
    area1 = w1 * h1
    area2 = w2 * h2
    union_area = area1 + area2 - inter_area
    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


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

    import imagehash
    from PIL import Image

    img_hashes: dict[Path, Any] = {}
    unreadable_count = 0
    tiny_count = 0
    oob_count = 0
    empty_labels_count = 0
    overlapping_count = 0

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
                safe_img_path = ensure_within_root(img_path, path)
                validate_file_size(safe_img_path)
                with Image.open(safe_img_path) as im:
                    image_sizes.append(im.size)
                    h = imagehash.phash(im)
                    img_hashes[img_path] = h
            except Exception:
                unreadable_count += 1
                warnings.append(f"Cannot read image: {img_path.name}")

        anns = parse_yolo_label(label_path) if label_exists else []
        bbox_counts_per_image.append(len(anns))
        total_annotations += len(anns)

        if label_exists:
            if label_path.stat().st_size == 0 or not anns:
                empty_labels_count += 1
            for i, box1 in enumerate(anns):
                cls1, cx1, cy1, w1, h1 = box1
                class_counts[cls1] = class_counts.get(cls1, 0) + 1
                bbox_areas.append(w1 * h1)

                if (
                    cx1 - w1 / 2 < 0.0
                    or cx1 + w1 / 2 > 1.0
                    or cy1 - h1 / 2 < 0.0
                    or cy1 + h1 / 2 > 1.0
                ):
                    oob_count += 1

                if w1 * h1 < 0.0005:
                    tiny_count += 1

                for j in range(i + 1, len(anns)):
                    box2 = anns[j]
                    cls2, cx2, cy2, w2, h2 = box2
                    if cls1 == cls2:
                        iou = _calculate_iou((cx1, cy1, w1, h1), (cx2, cy2, w2, h2))
                        if iou > 0.90:
                            overlapping_count += 1

    if total_images == 0:
        raise FovuxDatasetEmptyError(str(path))

    class_ids = sorted(set(class_counts) | set(range(len(class_names))))
    total_anns = sum(class_counts.values()) or 1
    classes = [
        ClassStat(
            name=class_names[idx] if idx < len(class_names) else f"class_{idx}",
            count=class_counts.get(idx, 0),
            pct=round(class_counts.get(idx, 0) / total_anns * 100, 2),
        )
        for idx in class_ids
    ]

    duplicate_groups: list[list[Path]] = []
    used_indices = set()
    hash_list = list(img_hashes.items())
    for i, (p1, h1) in enumerate(hash_list):
        if i in used_indices:
            continue
        group = [p1]
        for j in range(i + 1, len(hash_list)):
            if j in used_indices:
                continue
            p2, h2 = hash_list[j]
            dist = int(h1 - h2)
            if dist <= 5:
                group.append(p2)
                used_indices.add(j)
        if len(group) > 1:
            used_indices.add(i)
            duplicate_groups.append(group)

    leaked_issues = []
    from fovux.tools.dataset_find_duplicates import _split_key

    for group in duplicate_groups:
        splits: dict[str, list[Path]] = {}
        for p in group:
            sp = _split_key(path, p)
            splits.setdefault(sp, []).append(p)
        if len(splits) > 1:
            train_imgs = splits.get("train", [])
            val_imgs = splits.get("val", [])
            test_imgs = splits.get("test", [])
            for t_img in train_imgs or [group[0]]:
                for v_img in val_imgs:
                    leaked_issues.append(
                        LeakageIssue(
                            train_image=str(t_img.relative_to(path)),
                            val_image=str(v_img.relative_to(path)),
                            reason="Train image is duplicated in validation set.",
                        )
                    )
                for ts_img in test_imgs:
                    leaked_issues.append(
                        LeakageIssue(
                            train_image=str(t_img.relative_to(path)),
                            test_image=str(ts_img.relative_to(path)),
                            reason="Train image is duplicated in test set.",
                        )
                    )

    quality_score, auto_fix_plan, dataset_card, class_balance_gini = _compute_quality_intelligence(
        path=path,
        fmt=fmt,
        total_images=total_images,
        total_annotations=total_annotations,
        classes=classes,
        class_ids=class_ids,
        class_counts=class_counts,
        duplicate_groups=duplicate_groups,
        leaked_issues=leaked_issues,
        unreadable_count=unreadable_count,
        tiny_count=tiny_count,
        oob_count=oob_count,
        empty_labels_count=empty_labels_count,
        overlapping_count=overlapping_count,
    )

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
        num_classes=len(class_ids),
        classes=classes,
        image_size_distribution=img_size_hist,
        bbox_size_distribution=bbox_size_hist,
        bbox_size_buckets=_normalized_bbox_size_buckets(bbox_areas),
        bbox_count_per_image=bbox_count_hist,
        orphan_images=orphan_images,
        missing_label_images=missing_label_images,
        orphan_annotations=orphan_annotations,
        class_balance_gini=class_balance_gini,
        splits_detected=splits_detected,
        warnings=warnings,
        sample_paths=sample_paths,
        analysis_duration_seconds=round(time.perf_counter() - t0, 3),
        quality_score=quality_score,
        label_anomalies=LabelAnomalySummary(
            tiny_boxes=tiny_count,
            out_of_bounds=oob_count,
            empty_labels=empty_labels_count,
            suspiciously_overlapping=overlapping_count,
        ),
        duplicate_groups_count=len(duplicate_groups),
        total_duplicates_found=sum(len(g) for g in duplicate_groups),
        leaked_images=leaked_issues,
        auto_fix_plan=auto_fix_plan,
        dataset_card=dataset_card,
    )


def _compute_quality_intelligence(
    path: Path,
    fmt: str,
    total_images: int,
    total_annotations: int,
    classes: list[ClassStat],
    class_ids: list[int],
    class_counts: dict[int, int],
    duplicate_groups: list[list[Path]],
    leaked_issues: list[LeakageIssue],
    unreadable_count: int,
    tiny_count: int,
    oob_count: int,
    empty_labels_count: int,
    overlapping_count: int,
) -> tuple[float, list[AutoFixItem], str, float]:
    class_balance_gini = gini([class_counts.get(idx, 0) for idx in class_ids])

    quality_score = 100.0
    quality_score -= class_balance_gini * 30.0
    pct_corrupt = (unreadable_count / total_images) if total_images > 0 else 0.0
    quality_score -= pct_corrupt * 200.0
    total_dups = sum(len(g) for g in duplicate_groups)
    pct_dup = (total_dups / total_images) if total_images > 0 else 0.0
    quality_score -= pct_dup * 150.0
    if leaked_issues:
        quality_score -= 25.0
    total_anomalies = tiny_count + oob_count + empty_labels_count + overlapping_count
    if total_anomalies > 0:
        quality_score -= min(total_anomalies * 1.0, 10.0)
    quality_score = max(0.0, min(100.0, round(quality_score, 1)))

    auto_fix_plan = []
    if total_dups > 0:
        auto_fix_plan.append(
            AutoFixItem(
                action="Remove duplicate images",
                description=(
                    f"Identified {total_dups} duplicate or near-duplicate images across splits."
                ),
                estimated_impact=(
                    "Reduces training overfitting and evaluation bias, improving generalization."
                ),
            )
        )
    if leaked_issues:
        auto_fix_plan.append(
            AutoFixItem(
                action="Remove train-val/test leakage",
                description=f"Found {len(leaked_issues)} images leaked across different splits.",
                estimated_impact=(
                    "Eliminates evaluation metric inflation, providing honest test performance."
                ),
            )
        )
    if oob_count > 0:
        auto_fix_plan.append(
            AutoFixItem(
                action="Clip out-of-bounds bounding boxes",
                description=f"Found {oob_count} bounding boxes escaping image limits.",
                estimated_impact=(
                    "Stabilizes YOLO regression loss and prevents infinite gradient issues "
                    "during training."
                ),
            )
        )
    if tiny_count > 0:
        auto_fix_plan.append(
            AutoFixItem(
                action="Filter tiny bounding boxes",
                description=(
                    f"Identified {tiny_count} bounding boxes smaller than 0.05% of the image size."
                ),
                estimated_impact=(
                    "Removes potential background noise or labelling mistakes, "
                    "speeding up convergence."
                ),
            )
        )
    if overlapping_count > 0:
        auto_fix_plan.append(
            AutoFixItem(
                action="Merge overlapping bounding boxes",
                description=(
                    f"Found {overlapping_count} duplicate bounding boxes with IoU > 90% "
                    "in the same class."
                ),
                estimated_impact="Reduces model confusion and multi-detection penalties.",
            )
        )
    if class_balance_gini > 0.4:
        auto_fix_plan.append(
            AutoFixItem(
                action="Rebalance class distribution",
                description=(
                    f"Dataset is highly imbalanced (Gini coefficient: {class_balance_gini:.2f})."
                ),
                estimated_impact=(
                    "Oversample minority classes or apply data augmentation to improve "
                    "minority class recall."
                ),
            )
        )

    dataset_card = f"""# Dataset Card: {path.name}

## Dataset Summary
- **Format:** {fmt.upper()}
- **Total Images:** {total_images}
- **Total Annotations:** {total_annotations}
- **Number of Classes:** {len(classes)}

## Quality Assessment
- **Quality Score:** {quality_score}/100
- **Class Balance (Gini):** {class_balance_gini:.3f} (0=balanced, 1=imbalanced)
- **Leaked Images:** {len(leaked_issues)}
- **Duplicates Found:** {total_dups} in {len(duplicate_groups)} groups

## Label Health & Anomalies
- **Tiny Boxes:** {tiny_count}
- **Out of Bounds Boxes:** {oob_count}
- **Empty Annotation Files:** {empty_labels_count}
- **Suspiciously Overlapping Annotations:** {overlapping_count}

## Recommendations & Auto-Fix Plan
"""
    if auto_fix_plan:
        for idx, item in enumerate(auto_fix_plan, 1):
            detail_line = (
                f"{idx}. **{item.action}**\n"
                f"   - *Detail:* {item.description}\n"
                f"   - *Impact:* {item.estimated_impact}\n"
            )
            dataset_card += detail_line
    else:
        dataset_card += "No auto-fix actions recommended. Dataset quality is excellent!"

    return quality_score, auto_fix_plan, dataset_card, class_balance_gini


def _calculate_coco_iou(
    box1: tuple[float, float, float, float], box2: tuple[float, float, float, float]
) -> float:
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    inter_x1 = max(x1, x2)
    inter_y1 = max(y1, y2)
    inter_x2 = min(x1 + w1, x2 + w2)
    inter_y2 = min(y1 + h1, y2 + h2)
    if inter_x1 < inter_x2 and inter_y1 < inter_y2:
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    else:
        inter_area = 0.0
    area1 = w1 * h1
    area2 = w2 * h2
    union_area = area1 + area2 - inter_area
    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


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

    import imagehash
    from PIL import Image

    img_hashes: dict[Path, Any] = {}
    unreadable_count = 0
    tiny_count = 0
    oob_count = 0
    empty_labels_count = 0
    overlapping_count = 0

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
        if not images_dir.is_dir():
            images_dir = path

        for img_info in imgs[: inp.max_images_analyzed]:
            file_name = img_info.get("file_name", "")
            img_path = images_dir / file_name
            if img_path.exists():
                if len(sample_paths) < 10:
                    sample_paths.append(img_path)
                try:
                    safe_img_path = ensure_within_root(img_path, path)
                    validate_file_size(safe_img_path)
                    with Image.open(safe_img_path) as im:
                        h = imagehash.phash(im)
                        img_hashes[img_path] = h
                except Exception:
                    unreadable_count += 1
                    warnings.append(f"Cannot read image: {file_name}")

        img_id_to_size = {img.get("id"): (img.get("width"), img.get("height")) for img in imgs}
        ann_list = data.get("annotations", [])
        total_annotations += len(ann_list)

        anns_by_img: dict[int, list[dict[str, Any]]] = {}
        for ann in ann_list:
            img_id = ann.get("image_id")
            if img_id is not None:
                anns_by_img.setdefault(img_id, []).append(ann)

        for img in imgs:
            img_id = img.get("id")
            if img_id not in anns_by_img or not anns_by_img[img_id]:
                empty_labels_count += 1

        for img_id, img_anns in anns_by_img.items():
            img_size = img_id_to_size.get(img_id, (None, None))
            img_w, img_h = img_size
            bbox_per_img[img_id] = len(img_anns)

            for i, ann1 in enumerate(img_anns):
                cat_id1 = ann1.get("category_id", 0)
                class_counts[cat_id1] = class_counts.get(cat_id1, 0) + 1
                bbox1 = ann1.get("bbox", [0, 0, 1, 1])
                if len(bbox1) >= 4:
                    x1, y1, w1, h1 = (
                        float(bbox1[0]),
                        float(bbox1[1]),
                        float(bbox1[2]),
                        float(bbox1[3]),
                    )
                    area1 = w1 * h1
                    bbox_areas.append(area1)

                    if img_w and img_h:
                        if x1 < 0 or y1 < 0 or x1 + w1 > img_w or y1 + h1 > img_h:
                            oob_count += 1
                        if (area1 / (img_w * img_h)) < 0.0005:
                            tiny_count += 1
                    else:
                        if x1 < 0 or y1 < 0:
                            oob_count += 1
                        if area1 < 100:
                            tiny_count += 1

                    for j in range(i + 1, len(img_anns)):
                        ann2 = img_anns[j]
                        cat_id2 = ann2.get("category_id", 0)
                        if cat_id1 == cat_id2:
                            bbox2 = ann2.get("bbox", [0, 0, 1, 1])
                            if len(bbox2) >= 4:
                                x2, y2, w2, h2 = (
                                    float(bbox2[0]),
                                    float(bbox2[1]),
                                    float(bbox2[2]),
                                    float(bbox2[3]),
                                )
                                iou = _calculate_coco_iou((x1, y1, w1, h1), (x2, y2, w2, h2))
                                if iou > 0.90:
                                    overlapping_count += 1

    if total_images == 0:
        raise FovuxDatasetEmptyError(str(path))

    class_ids = sorted(set(class_counts) | set(id_to_name))
    total_anns = sum(class_counts.values()) or 1
    classes = [
        ClassStat(
            name=id_to_name.get(cid, f"class_{cid}"),
            count=class_counts.get(cid, 0),
            pct=round(class_counts.get(cid, 0) / total_anns * 100, 2),
        )
        for cid in class_ids
    ]

    duplicate_groups: list[list[Path]] = []
    used_indices = set()
    hash_list = list(img_hashes.items())
    for i, (p1, h1) in enumerate(hash_list):
        if i in used_indices:
            continue
        group = [p1]
        for j in range(i + 1, len(hash_list)):
            if j in used_indices:
                continue
            p2, h2 = hash_list[j]
            dist = int(h1 - h2)
            if dist <= 5:
                group.append(p2)
                used_indices.add(j)
        if len(group) > 1:
            used_indices.add(i)
            duplicate_groups.append(group)

    leaked_issues = []
    from fovux.tools.dataset_find_duplicates import _split_key

    for group in duplicate_groups:
        splits: dict[str, list[Path]] = {}
        for p in group:
            sp = _split_key(path, p)
            splits.setdefault(sp, []).append(p)
        if len(splits) > 1:
            train_imgs = splits.get("train", [])
            val_imgs = splits.get("val", [])
            test_imgs = splits.get("test", [])
            for t_img in train_imgs or [group[0]]:
                for v_img in val_imgs:
                    leaked_issues.append(
                        LeakageIssue(
                            train_image=str(t_img.relative_to(path)),
                            val_image=str(v_img.relative_to(path)),
                            reason="Train image is duplicated in validation set.",
                        )
                    )
                for ts_img in test_imgs:
                    leaked_issues.append(
                        LeakageIssue(
                            train_image=str(t_img.relative_to(path)),
                            test_image=str(ts_img.relative_to(path)),
                            reason="Train image is duplicated in test set.",
                        )
                    )

    quality_score, auto_fix_plan, dataset_card, class_balance_gini = _compute_quality_intelligence(
        path=path,
        fmt=fmt,
        total_images=total_images,
        total_annotations=total_annotations,
        classes=classes,
        class_ids=class_ids,
        class_counts=class_counts,
        duplicate_groups=duplicate_groups,
        leaked_issues=leaked_issues,
        unreadable_count=unreadable_count,
        tiny_count=tiny_count,
        oob_count=oob_count,
        empty_labels_count=empty_labels_count,
        overlapping_count=overlapping_count,
    )

    bal, bac = bucket_distribution(bbox_areas)
    bcl, bcc = bucket_distribution([float(v) for v in bbox_per_img.values()])

    return DatasetInspectOutput(
        format_detected=fmt,
        total_images=total_images,
        total_annotations=total_annotations,
        num_classes=len(class_ids),
        classes=classes,
        image_size_distribution=SizeHistogram(buckets=["N/A"], counts=[total_images]),
        bbox_size_distribution=SizeHistogram(buckets=bal or ["N/A"], counts=bac or [0]),
        bbox_size_buckets={},
        bbox_count_per_image=Histogram(buckets=bcl or ["0"], counts=bcc or [0]),
        orphan_images=0,
        missing_label_images=[],
        orphan_annotations=0,
        class_balance_gini=class_balance_gini,
        splits_detected=splits_detected,
        warnings=warnings,
        sample_paths=sample_paths,
        analysis_duration_seconds=round(time.perf_counter() - t0, 3),
        quality_score=quality_score,
        label_anomalies=LabelAnomalySummary(
            tiny_boxes=tiny_count,
            out_of_bounds=oob_count,
            empty_labels=empty_labels_count,
            suspiciously_overlapping=overlapping_count,
        ),
        duplicate_groups_count=len(duplicate_groups),
        total_duplicates_found=sum(len(g) for g in duplicate_groups),
        leaked_images=leaked_issues,
        auto_fix_plan=auto_fix_plan,
        dataset_card=dataset_card,
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

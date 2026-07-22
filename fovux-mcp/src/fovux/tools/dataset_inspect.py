"""dataset_inspect — shared statistics over a normalized dataset inventory."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fovux.core.dataset_analysis import InventoryAnalysis, analyze_dataset_inventory
from fovux.core.dataset_inventory import DatasetInventory, build_dataset_inventory
from fovux.core.dataset_utils import bucket_distribution, detect_format, gini
from fovux.core.errors import (
    FovuxDatasetFormatError,
    FovuxDatasetNotFoundError,
)
from fovux.core.tooling import tool_event
from fovux.core.validation import resolve_local_path
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
    started_at = time.perf_counter()
    path = resolve_local_path(inp.dataset_path)
    if not path.exists():
        raise FovuxDatasetNotFoundError(str(path))

    fmt = inp.format if inp.format != "auto" else detect_format(path)
    if fmt not in {"yolo", "coco"}:
        raise FovuxDatasetFormatError(
            f"dataset_inspect currently supports YOLO and COCO datasets; received '{fmt}'.",
            hint="Convert the dataset to YOLO or COCO before inspection.",
        )
    inventory = build_dataset_inventory(
        path,
        fmt,
        analyze_images=True,
        compute_fingerprints=True,
        max_images_analyzed=inp.max_images_analyzed,
    )
    return _inspect_inventory(inventory, inp, started_at)


def _inspect_inventory(
    inventory: DatasetInventory,
    inp: DatasetInspectInput,
    started_at: float,
) -> DatasetInspectOutput:
    analysis = analyze_dataset_inventory(inventory)
    classes = _build_class_statistics(inventory, analysis)
    leaked_images = _build_leakage_issues(inventory, analysis)
    quality_score, auto_fix_plan, dataset_card, class_balance_gini = _quality_intelligence(
        inventory=inventory,
        analysis=analysis,
        classes=classes,
        leaked_images=leaked_images,
    )

    warnings = list(inventory.warnings)
    warnings.extend(
        f"Cannot read image: {image.path.name}"
        for image in inventory.images
        if image.analyzed and image.readable is False
    )
    sample_paths = (
        [image.path for image in inventory.images if image.analyzed and image.exists][:10]
        if inp.include_samples
        else []
    )
    image_size_histogram = _image_size_histogram(inventory, analysis)
    bbox_size_histogram = _bbox_size_histogram(inventory, analysis)
    bbox_count_values = analysis.annotation_counts
    if inventory.format == "coco":
        bbox_count_values = [value for value in bbox_count_values if value > 0]
    bbox_count_labels, bbox_count_counts = bucket_distribution(
        [float(value) for value in bbox_count_values]
    )

    return DatasetInspectOutput(
        format_detected=inventory.format,
        total_images=len(inventory.images),
        total_annotations=len(inventory.annotations),
        num_classes=len(analysis.class_ids),
        classes=classes,
        image_size_distribution=image_size_histogram,
        bbox_size_distribution=bbox_size_histogram,
        bbox_size_buckets=(
            _normalized_bbox_size_buckets(analysis.normalized_bbox_areas)
            if inventory.format == "yolo"
            else {}
        ),
        bbox_count_per_image=Histogram(
            buckets=bbox_count_labels or ["0"],
            counts=bbox_count_counts
            or ([len(inventory.images)] if inventory.format == "yolo" else [0]),
        ),
        orphan_images=len(inventory.missing_annotation_images),
        missing_label_images=inventory.missing_annotation_images,
        orphan_annotations=len(inventory.orphan_annotation_sources),
        class_balance_gini=class_balance_gini,
        splits_detected=inventory.splits,
        warnings=warnings,
        sample_paths=sample_paths,
        analysis_duration_seconds=round(time.perf_counter() - started_at, 3),
        quality_score=quality_score,
        label_anomalies=LabelAnomalySummary(
            tiny_boxes=analysis.tiny_count,
            out_of_bounds=analysis.out_of_bounds_count,
            empty_labels=analysis.empty_annotation_count,
            suspiciously_overlapping=analysis.overlapping_count,
        ),
        duplicate_groups_count=len(analysis.duplicate_groups),
        total_duplicates_found=sum(len(group) for group in analysis.duplicate_groups),
        leaked_images=leaked_images,
        auto_fix_plan=auto_fix_plan,
        dataset_card=dataset_card,
    )


def _build_class_statistics(
    inventory: DatasetInventory,
    analysis: InventoryAnalysis,
) -> list[ClassStat]:
    total_annotations = sum(analysis.class_counts.values()) or 1
    return [
        ClassStat(
            name=inventory.class_names.get(class_id, f"class_{class_id}"),
            count=analysis.class_counts.get(class_id, 0),
            pct=round(analysis.class_counts.get(class_id, 0) / total_annotations * 100, 2),
        )
        for class_id in analysis.class_ids
    ]


def _build_leakage_issues(
    inventory: DatasetInventory,
    analysis: InventoryAnalysis,
) -> list[LeakageIssue]:
    issues: list[LeakageIssue] = []
    for item in analysis.leakage:
        if item.val_image is not None:
            issues.append(
                LeakageIssue(
                    train_image=_relative_path(inventory, item.train_image),
                    val_image=_relative_path(inventory, item.val_image),
                    reason="Train image is duplicated in validation set.",
                )
            )
        if item.test_image is not None:
            issues.append(
                LeakageIssue(
                    train_image=_relative_path(inventory, item.train_image),
                    test_image=_relative_path(inventory, item.test_image),
                    reason="Train image is duplicated in test set.",
                )
            )
    return issues


def _relative_path(inventory: DatasetInventory, path: Path) -> str:
    try:
        return str(path.relative_to(inventory.root))
    except ValueError:
        return str(path)


def _image_size_histogram(
    inventory: DatasetInventory,
    analysis: InventoryAnalysis,
) -> SizeHistogram:
    if inventory.format == "coco":
        return SizeHistogram(buckets=["N/A"], counts=[len(inventory.images)])
    labels, counts = bucket_distribution(analysis.image_widths)
    return SizeHistogram(buckets=labels or ["N/A"], counts=counts or [0])


def _bbox_size_histogram(
    inventory: DatasetInventory,
    analysis: InventoryAnalysis,
) -> SizeHistogram:
    values = (
        [area * 100 for area in analysis.normalized_bbox_areas]
        if inventory.format == "yolo"
        else analysis.raw_bbox_areas
    )
    labels, counts = bucket_distribution(values)
    return SizeHistogram(buckets=labels or ["N/A"], counts=counts or [0])


def _quality_intelligence(
    *,
    inventory: DatasetInventory,
    analysis: InventoryAnalysis,
    classes: list[ClassStat],
    leaked_images: list[LeakageIssue],
) -> tuple[float, list[AutoFixItem], str, float]:
    class_balance_gini = gini(
        [analysis.class_counts.get(class_id, 0) for class_id in analysis.class_ids]
    )
    total_images = len(inventory.images)
    total_duplicates = sum(len(group) for group in analysis.duplicate_groups)
    quality_score = 100.0
    quality_score -= class_balance_gini * 30.0
    quality_score -= (analysis.unreadable_count / total_images if total_images else 0.0) * 200.0
    quality_score -= (total_duplicates / total_images if total_images else 0.0) * 150.0
    if leaked_images:
        quality_score -= 25.0
    anomaly_count = (
        analysis.tiny_count
        + analysis.out_of_bounds_count
        + analysis.empty_annotation_count
        + analysis.overlapping_count
    )
    quality_score -= min(float(anomaly_count), 10.0)
    quality_score = max(0.0, min(100.0, round(quality_score, 1)))

    auto_fix_plan = _auto_fix_plan(
        analysis=analysis,
        total_duplicates=total_duplicates,
        leaked_images=leaked_images,
        class_balance_gini=class_balance_gini,
    )
    dataset_card = _dataset_card(
        inventory=inventory,
        analysis=analysis,
        classes=classes,
        leaked_images=leaked_images,
        total_duplicates=total_duplicates,
        quality_score=quality_score,
        class_balance_gini=class_balance_gini,
        auto_fix_plan=auto_fix_plan,
    )
    return quality_score, auto_fix_plan, dataset_card, class_balance_gini


def _auto_fix_plan(
    *,
    analysis: InventoryAnalysis,
    total_duplicates: int,
    leaked_images: list[LeakageIssue],
    class_balance_gini: float,
) -> list[AutoFixItem]:
    plan: list[AutoFixItem] = []
    if total_duplicates:
        plan.append(
            AutoFixItem(
                action="Remove duplicate images",
                description=(
                    f"Identified {total_duplicates} duplicate or near-duplicate images "
                    "across splits."
                ),
                estimated_impact=(
                    "Reduces training overfitting and evaluation bias, improving generalization."
                ),
            )
        )
    if leaked_images:
        plan.append(
            AutoFixItem(
                action="Remove train-val/test leakage",
                description=f"Found {len(leaked_images)} images leaked across different splits.",
                estimated_impact=(
                    "Eliminates evaluation metric inflation, providing honest test performance."
                ),
            )
        )
    if analysis.out_of_bounds_count:
        plan.append(
            AutoFixItem(
                action="Clip out-of-bounds bounding boxes",
                description=(
                    f"Found {analysis.out_of_bounds_count} bounding boxes escaping image limits."
                ),
                estimated_impact=(
                    "Stabilizes YOLO regression loss and prevents infinite gradient issues "
                    "during training."
                ),
            )
        )
    if analysis.tiny_count:
        plan.append(
            AutoFixItem(
                action="Filter tiny bounding boxes",
                description=(
                    f"Identified {analysis.tiny_count} bounding boxes smaller than 0.05% "
                    "of the image size."
                ),
                estimated_impact=(
                    "Removes potential background noise or labelling mistakes, "
                    "speeding up convergence."
                ),
            )
        )
    if analysis.overlapping_count:
        plan.append(
            AutoFixItem(
                action="Merge overlapping bounding boxes",
                description=(
                    f"Found {analysis.overlapping_count} duplicate bounding boxes with IoU > 90% "
                    "in the same class."
                ),
                estimated_impact="Reduces model confusion and multi-detection penalties.",
            )
        )
    if class_balance_gini > 0.4:
        plan.append(
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
    return plan


def _dataset_card(
    *,
    inventory: DatasetInventory,
    analysis: InventoryAnalysis,
    classes: list[ClassStat],
    leaked_images: list[LeakageIssue],
    total_duplicates: int,
    quality_score: float,
    class_balance_gini: float,
    auto_fix_plan: list[AutoFixItem],
) -> str:
    card = f"""# Dataset Card: {inventory.root.name}

## Dataset Summary
- **Format:** {inventory.format.upper()}
- **Total Images:** {len(inventory.images)}
- **Total Annotations:** {len(inventory.annotations)}
- **Number of Classes:** {len(classes)}

## Quality Assessment
- **Quality Score:** {quality_score}/100
- **Class Balance (Gini):** {class_balance_gini:.3f} (0=balanced, 1=imbalanced)
- **Leaked Images:** {len(leaked_images)}
- **Duplicates Found:** {total_duplicates} in {len(analysis.duplicate_groups)} groups

## Label Health & Anomalies
- **Tiny Boxes:** {analysis.tiny_count}
- **Out of Bounds Boxes:** {analysis.out_of_bounds_count}
- **Empty Annotation Files:** {analysis.empty_annotation_count}
- **Suspiciously Overlapping Annotations:** {analysis.overlapping_count}

## Recommendations & Auto-Fix Plan
"""
    if not auto_fix_plan:
        return card + "No auto-fix actions recommended. Dataset quality is excellent!"
    for index, item in enumerate(auto_fix_plan, 1):
        card += (
            f"{index}. **{item.action}**\n"
            f"   - *Detail:* {item.description}\n"
            f"   - *Impact:* {item.estimated_impact}\n"
        )
    return card


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

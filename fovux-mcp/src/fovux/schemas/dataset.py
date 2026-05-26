"""Pydantic schemas for dataset tools."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

AugmentationTechnique = Literal["flip_h", "flip_v", "cutout", "mosaic", "mixup"]


def default_augmentation_techniques() -> list[AugmentationTechnique]:
    """Return the default deterministic augmentation list."""
    return ["flip_h"]


class ClassStat(BaseModel):
    """Statistics for a single class."""

    name: str
    count: int
    pct: float
    avg_bbox_area: float | None = None


class SizeHistogram(BaseModel):
    """Simple histogram for size distributions."""

    buckets: list[str]
    counts: list[int]


class Histogram(BaseModel):
    """Generic histogram."""

    buckets: list[str]
    counts: list[int]


class DatasetInspectInput(BaseModel):
    """Input for dataset_inspect tool."""

    dataset_path: Path
    format: Literal["yolo", "coco", "voc", "auto"] = "auto"
    include_samples: bool = True
    max_images_analyzed: int = 10_000


class DatasetInspectOutput(BaseModel):
    """Output from dataset_inspect tool."""

    format_detected: str
    total_images: int
    total_annotations: int
    num_classes: int
    classes: list[ClassStat]
    image_size_distribution: SizeHistogram
    bbox_size_distribution: SizeHistogram
    bbox_size_buckets: dict[str, int] = Field(default_factory=dict)
    bbox_count_per_image: Histogram
    orphan_images: int
    missing_label_images: list[Path] = Field(default_factory=list)
    orphan_annotations: int
    class_balance_gini: float
    splits_detected: dict[str, int]
    warnings: list[str]
    sample_paths: list[Path]
    analysis_duration_seconds: float


class ValidationIssue(BaseModel):
    """A single validation issue."""

    file: str
    line: int | None = None
    severity: Literal["error", "warning"]
    message: str


class DatasetValidateInput(BaseModel):
    """Input for dataset_validate tool."""

    dataset_path: Path
    format: Literal["yolo", "coco", "voc", "auto"] = "auto"
    check_image_readable: bool = True
    check_bbox_bounds: bool = True
    check_class_id_range: bool = True
    strict: bool = False


class DatasetValidateOutput(BaseModel):
    """Output from dataset_validate tool."""

    valid: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    summary: str
    remediation_script: str | None = None


class DuplicateGroup(BaseModel):
    """A group of duplicate or near-duplicate images."""

    images: list[Path]
    hamming_distance: int


class DatasetFindDuplicatesInput(BaseModel):
    """Input for dataset_find_duplicates tool."""

    dataset_path: Path
    algorithm: Literal["phash", "dhash", "whash", "avg"] = "phash"
    hamming_threshold: int = 5
    across_splits: bool = True


class DatasetFindDuplicatesOutput(BaseModel):
    """Output from dataset_find_duplicates tool."""

    total_images: int
    duplicate_groups: list[DuplicateGroup]
    total_duplicates: int
    duplicate_pct: float
    analysis_duration_seconds: float


class DatasetSplitInput(BaseModel):
    """Input for dataset_split tool."""

    dataset_path: Path
    ratios: tuple[float, float, float] = (0.7, 0.2, 0.1)
    stratify_by_class: bool = True
    seed: int = 42
    output_format: Literal["yolo", "coco"] = "yolo"
    overwrite: bool = False
    output_path: Path | None = None


class DatasetSplitOutput(BaseModel):
    """Output from dataset_split tool."""

    train_count: int
    val_count: int
    test_count: int
    stratification_report: dict[str, dict[str, int]]
    output_path: Path
    manifest_path: Path


class DatasetConvertInput(BaseModel):
    """Input for dataset_convert tool."""

    source_path: Path
    source_format: Literal["yolo", "coco", "voc", "auto"] = "auto"
    target_format: Literal["yolo", "coco", "voc"]
    target_path: Path
    copy_images: bool = False
    class_map: dict[str, str] | None = None


class DatasetConvertOutput(BaseModel):
    """Output from dataset_convert tool."""

    images_processed: int
    annotations_converted: int
    annotations_skipped: int
    skip_reasons: dict[str, int]
    target_path: Path
    conversion_duration_seconds: float


class DatasetAugmentInput(BaseModel):
    """Input for dataset_augment."""

    dataset_path: Path
    techniques: list[AugmentationTechnique] = Field(default_factory=default_augmentation_techniques)
    multiplier: int = 3
    output_path: Path


class DatasetAugmentOutput(BaseModel):
    """Output from dataset_augment."""

    dataset_path: Path
    output_path: Path
    source_images: int
    generated_images: int
    techniques: list[str]
    manifest_path: Path

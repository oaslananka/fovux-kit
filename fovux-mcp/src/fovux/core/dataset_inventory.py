"""Normalized dataset inventory shared by inspect and validate flows."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from fovux.core.errors import FovuxDatasetFormatError

DatasetFormat = Literal["yolo", "coco"]
FindingSeverity = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class NormalizedBoundingBox:
    """Top-left/bottom-right box in image-relative coordinates."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        """Return the non-negative normalized width."""
        return max(0.0, self.x_max - self.x_min)

    @property
    def height(self) -> float:
        """Return the non-negative normalized height."""
        return max(0.0, self.y_max - self.y_min)

    @property
    def area_ratio(self) -> float:
        """Return the box area as a fraction of image area."""
        return self.width * self.height

    @property
    def is_within_bounds(self) -> bool:
        """Return whether the box is non-empty and contained in ``[0, 1]``."""
        return 0.0 <= self.x_min < self.x_max <= 1.0 and 0.0 <= self.y_min < self.y_max <= 1.0


@dataclass(frozen=True, slots=True)
class DatasetFinding:
    """Format-neutral issue found while adapting a dataset."""

    code: str
    severity: FindingSeverity
    message: str
    file: Path
    line: int | None = None


@dataclass(frozen=True, slots=True)
class ImageRecord:
    """One declared or discovered image."""

    image_id: str
    path: Path
    split: str
    width: int | None
    height: int | None
    annotation_source: Path | None
    annotation_source_exists: bool
    analyzed: bool
    exists: bool
    readable: bool | None = None
    fingerprint: str | None = None
    analysis_error: str | None = None


@dataclass(frozen=True, slots=True)
class AnnotationRecord:
    """One format-neutral object annotation."""

    image_id: str
    image_path: Path | None
    class_id: int
    source_path: Path
    line: int | None
    bbox: NormalizedBoundingBox | None
    raw_bbox: tuple[float, float, float, float]
    raw_area: float


@dataclass(slots=True)
class DatasetInventory:
    """Normalized contract consumed by analysis and validation."""

    root: Path
    format: DatasetFormat
    class_names: dict[int, str]
    images: list[ImageRecord]
    annotations: list[AnnotationRecord]
    splits: dict[str, int]
    findings: list[DatasetFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    orphan_annotation_sources: list[Path] = field(default_factory=list)
    declared_class_count: int | None = None

    @property
    def class_counts(self) -> dict[int, int]:
        """Return annotation counts keyed by class ID."""
        return dict(Counter(annotation.class_id for annotation in self.annotations))

    @property
    def annotation_counts_by_image(self) -> dict[str, int]:
        """Return annotation counts keyed by normalized image ID."""
        counts = Counter(annotation.image_id for annotation in self.annotations)
        return {image.image_id: counts.get(image.image_id, 0) for image in self.images}

    @property
    def annotation_counts_per_image(self) -> list[int]:
        """Return annotation counts in deterministic image order."""
        counts = self.annotation_counts_by_image
        return [counts[image.image_id] for image in self.images]

    @property
    def bbox_area_ratios(self) -> list[float]:
        """Return normalized areas for annotations with image-relative boxes."""
        return [
            annotation.bbox.area_ratio
            for annotation in self.annotations
            if annotation.bbox is not None
        ]

    @property
    def missing_annotation_images(self) -> list[Path]:
        """Return images whose format-specific annotation source is missing."""
        return [
            image.path
            for image in self.images
            if image.annotation_source is not None and not image.annotation_source_exists
        ]


class DatasetFormatAdapter(Protocol):
    """Extension point implemented by each dataset format."""

    format_name: DatasetFormat

    def build(
        self,
        root: Path,
        *,
        analyze_images: bool,
        compute_fingerprints: bool,
        max_images_analyzed: int,
    ) -> DatasetInventory:
        """Translate a format-specific dataset into a normalized inventory."""
        ...


_ADAPTERS: dict[str, type[DatasetFormatAdapter]] = {}


def register_dataset_adapter(
    format_name: DatasetFormat,
    adapter_type: type[DatasetFormatAdapter],
) -> None:
    """Register a normalized format adapter."""
    _ADAPTERS[format_name] = adapter_type


def registered_dataset_formats() -> tuple[str, ...]:
    """Return deterministic registered format names."""
    _ensure_builtin_adapters()
    return tuple(sorted(_ADAPTERS))


def build_dataset_inventory(
    dataset_path: Path,
    format_name: str,
    *,
    analyze_images: bool = True,
    compute_fingerprints: bool = True,
    max_images_analyzed: int = 10_000,
) -> DatasetInventory:
    """Translate a YOLO or COCO dataset into the shared inventory model."""
    _ensure_builtin_adapters()
    adapter_type = _ADAPTERS.get(format_name)
    if adapter_type is None:
        raise FovuxDatasetFormatError(
            f"No normalized inventory adapter is registered for '{format_name}'.",
            hint=f"Use one of: {', '.join(registered_dataset_formats())}.",
        )
    return adapter_type().build(
        dataset_path.resolve(strict=False),
        analyze_images=analyze_images,
        compute_fingerprints=compute_fingerprints,
        max_images_analyzed=max_images_analyzed,
    )


def _ensure_builtin_adapters() -> None:
    if _ADAPTERS:
        return
    from fovux.core.dataset_adapters import CocoDatasetAdapter, YoloDatasetAdapter

    register_dataset_adapter("coco", CocoDatasetAdapter)
    register_dataset_adapter("yolo", YoloDatasetAdapter)

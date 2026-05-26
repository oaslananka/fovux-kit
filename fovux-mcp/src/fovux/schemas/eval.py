"""Pydantic schemas for evaluation tools."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class EvalRunInput(BaseModel):
    """Input for eval_run tool."""

    checkpoint: str
    dataset_path: Path
    split: str = "val"
    batch: int = 16
    imgsz: int = 640
    device: str = "auto"
    conf: float = 0.25
    iou: float = 0.45
    task: Literal["detect", "segment", "classify", "pose", "obb"] = "detect"


class PerClassStat(BaseModel):
    """Per-class evaluation statistics."""

    class_id: int
    class_name: str
    images: int
    instances: int
    precision: float
    recall: float
    map50: float
    map50_95: float


class EvalRunOutput(BaseModel):
    """Output from eval_run tool."""

    checkpoint: str
    dataset_path: Path
    split: str
    map50: float
    map50_95: float
    precision: float
    recall: float
    per_class: list[PerClassStat]
    eval_duration_seconds: float
    results_dir: Path | None = None


class EvalPerClassInput(BaseModel):
    """Input for eval_per_class tool."""

    checkpoint: str
    dataset_path: Path
    split: str = "val"
    batch: int = 16
    imgsz: int = 640
    device: str = "auto"
    conf: float = 0.25
    iou: float = 0.45
    sort_by: Literal["map50", "map50_95", "precision", "recall", "class_name"] = "map50"
    ascending: bool = True


class EvalPerClassOutput(BaseModel):
    """Output from eval_per_class tool."""

    checkpoint: str
    per_class: list[PerClassStat]
    worst_classes: list[PerClassStat]
    eval_duration_seconds: float


class ConfusionEntry(BaseModel):
    """A single confusion matrix entry."""

    true_class: str
    predicted_class: str
    count: int


class ErrorSample(BaseModel):
    """A high-error image sample."""

    image_path: Path
    true_class: str
    predicted_class: str
    confidence: float
    iou: float | None = None


class EvalErrorAnalysisInput(BaseModel):
    """Input for eval_error_analysis tool."""

    checkpoint: str
    dataset_path: Path
    split: str = "val"
    top_n: int = 10
    imgsz: int = 640
    device: str = "auto"
    conf: float = 0.25
    iou: float = 0.45


class EvalErrorAnalysisOutput(BaseModel):
    """Output from eval_error_analysis tool."""

    checkpoint: str
    confusion_matrix: list[ConfusionEntry]
    top_errors: list[ErrorSample]
    false_positive_count: int
    false_negative_count: int
    eval_duration_seconds: float


class EvalCompareInput(BaseModel):
    """Input for eval_compare tool."""

    checkpoints: list[str]
    dataset_path: Path
    split: str = "val"
    batch: int = 16
    imgsz: int = 640
    device: str = "auto"
    conf: float = 0.25
    iou: float = 0.45


class CheckpointComparison(BaseModel):
    """Comparison row for one checkpoint."""

    checkpoint: str
    map50: float
    map50_95: float
    precision: float
    recall: float
    eval_duration_seconds: float


class EvalCompareOutput(BaseModel):
    """Output from eval_compare tool."""

    dataset_path: Path
    split: str
    results: list[CheckpointComparison]
    best_map50: str
    best_map50_95: str

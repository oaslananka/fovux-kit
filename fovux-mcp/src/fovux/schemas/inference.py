"""Pydantic schemas for inference and latency benchmark tools."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Detection(BaseModel):
    """A single model detection."""

    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: list[float] = Field(default_factory=list)


class InferImageInput(BaseModel):
    """Input for infer_image."""

    checkpoint: str
    image_path: Path
    imgsz: int = 640
    conf: float = 0.25
    iou: float = 0.45
    device: str = "auto"
    save_image: bool = False
    output_path: Path | None = None


class InferImageOutput(BaseModel):
    """Output for infer_image."""

    checkpoint: str
    image_path: Path
    detections: list[Detection] = Field(default_factory=list)
    detection_count: int = 0
    detections_by_class: dict[str, int] = Field(default_factory=dict)
    inference_duration_seconds: float
    output_path: Path | None = None


class InferRtspInput(BaseModel):
    """Input for infer_rtsp."""

    checkpoint: str
    rtsp_url: str
    duration_seconds: int = 30
    imgsz: int = 640
    conf: float = 0.25
    save_video: bool = False
    output_path: Path | None = None
    frame_skip: int = 0
    device: str = "auto"
    max_reconnect_attempts: int = 10

    @model_validator(mode="after")
    def _validate_output(self) -> InferRtspInput:
        if self.save_video and self.output_path is None:
            raise ValueError("output_path is required when save_video=True")
        return self


class InferRtspOutput(BaseModel):
    """Output for infer_rtsp."""

    frames_processed: int
    frames_skipped: int
    dropped_frames: int
    avg_fps: float
    detection_count: int
    detections_by_class: dict[str, int] = Field(default_factory=dict)
    connection_status: str
    reconnect_attempts: int = 0
    output_fps: float = 0.0
    duration_actual_seconds: float
    output_path: Path | None = None


class BenchmarkLatencyInput(BaseModel):
    """Input for benchmark_latency."""

    model_path: Path
    backend: Literal["onnxruntime", "tflite", "tensorrt", "pytorch"] = "onnxruntime"
    device: str = "auto"
    imgsz: int = 640
    batch_size: int = 1
    num_warmup: int = 10
    num_iterations: int = 100
    threads: int = 4


class BatchDetectionSummary(BaseModel):
    """Per-image summary returned by infer_batch."""

    image_path: Path
    detection_count: int
    detections_by_class: dict[str, int] = Field(default_factory=dict)
    output_path: Path | None = None


class InferBatchInput(BaseModel):
    """Input for infer_batch."""

    checkpoint: str
    input_dir: Path
    output_dir: Path | None = None
    imgsz: int = 640
    conf: float = 0.25
    save_annotated: bool = True
    export_format: Literal["json", "csv", "yolo_labels"] = "json"
    device: str = "auto"
    batch_size: int = 32


class InferBatchOutput(BaseModel):
    """Output for infer_batch."""

    checkpoint: str
    input_dir: Path
    output_dir: Path | None = None
    export_format: str
    processed_images: int
    detection_count: int
    manifest_path: Path
    annotated_dir: Path | None = None
    preview: list[BatchDetectionSummary] = Field(default_factory=list)


class BenchmarkLatencyOutput(BaseModel):
    """Output for benchmark_latency."""

    backend: str
    device: str
    num_iterations: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_mean_ms: float
    latency_std_ms: float
    throughput_fps: float
    peak_memory_mb: float


class InferEnsembleInput(BaseModel):
    """Input for infer_ensemble."""

    checkpoints: list[str]
    image_path: Path
    fusion_method: Literal["wbf", "nms", "soft-nms"] = "wbf"
    weights: list[float] | None = None
    imgsz: int = 640
    conf: float = 0.25
    device: str = "auto"


class InferEnsembleOutput(BaseModel):
    """Output from infer_ensemble."""

    checkpoints: list[str]
    image_path: Path
    fusion_method: str
    detections: list[dict[str, object]] = Field(default_factory=list)
    detection_count: int = 0


class ModelCompareVisualInput(BaseModel):
    """Input for model_compare_visual."""

    checkpoint_a: str
    checkpoint_b: str
    image_path: Path
    output_path: Path | None = None
    imgsz: int = 640
    conf: float = 0.25
    device: str = "auto"


class ModelCompareVisualOutput(BaseModel):
    """Output from model_compare_visual."""

    checkpoint_a: str
    checkpoint_b: str
    image_path: Path
    output_path: Path
    detections_a: int
    detections_b: int


class ActiveLearningSelectInput(BaseModel):
    """Input for active_learning_select."""

    checkpoint: str
    unlabeled_pool: Path
    strategy: Literal["entropy", "margin", "least_confident"] = "entropy"
    budget: int = 100
    imgsz: int = 640
    conf: float = 0.25
    device: str = "auto"


class ActiveLearningSelectOutput(BaseModel):
    """Output from active_learning_select."""

    checkpoint: str
    strategy: str
    budget: int
    selected: list[dict[str, object]] = Field(default_factory=list)


class DistillModelInput(BaseModel):
    """Input for distill_model."""

    teacher_checkpoint: str
    student_model: str = "yolov8n.pt"
    dataset_path: Path
    temperature: float = 4.0
    alpha: float = 0.7
    epochs: int = 100
    batch: int = 16
    imgsz: int = 640
    device: str = "auto"
    name: str | None = None


class DistillModelOutput(BaseModel):
    """Output from distill_model."""

    run_id: str
    status: str
    pid: int | None
    run_path: Path
    teacher_checkpoint: str
    student_model: str


class TrainAdjustInput(BaseModel):
    """Input for train_adjust."""

    run_id: str
    learning_rate: float | None = None
    mosaic: bool | None = None


class TrainAdjustOutput(BaseModel):
    """Output from train_adjust."""

    run_id: str
    control_path: Path
    applied: dict[str, object]


class SyncToMlflowOutput(BaseModel):
    """Output from sync_to_mlflow."""

    run_id: str
    tracking_uri: str
    metrics_logged: int
    params_logged: int

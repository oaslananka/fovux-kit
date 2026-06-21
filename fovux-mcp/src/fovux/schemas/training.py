"""Pydantic schemas for training tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from fovux.schemas.common import RunId


class TrainingOptions(BaseModel):
    """Supported training options for YOLO."""

    model_config = {
        "extra": "forbid",
    }

    optimizer: Literal["SGD", "Adam", "AdamW", "RMSProp", "auto"] = "auto"
    lr0: float = Field(default=0.01, gt=0.0)
    lrf: float = Field(default=0.01, ge=0.0)
    momentum: float = Field(default=0.937, ge=0.0, le=1.0)
    weight_decay: float = Field(default=0.0005, ge=0.0)
    warmup_epochs: float = Field(default=3.0, ge=0.0)
    warmup_momentum: float = Field(default=0.8, ge=0.0, le=1.0)
    warmup_bias_lr: float = Field(default=0.1, ge=0.0)
    box: float = Field(default=7.5, ge=0.0)
    cls: float = Field(default=0.5, ge=0.0)
    dfl: float = Field(default=1.5, ge=0.0)
    pose: float = Field(default=12.0, ge=0.0)
    kobj: float = Field(default=1.0, ge=0.0)
    label_smoothing: float = Field(default=0.0, ge=0.0, le=1.0)
    nbs: int = Field(default=64, gt=0)
    overlap_mask: bool = True
    mask_ratio: int = Field(default=4, gt=0)
    dropout: float = Field(default=0.0, ge=0.0, le=1.0)
    val: bool = True
    save: bool = True
    save_period: int = Field(default=-1, ge=-1)
    cache: Literal["ram", "disk", "auto", ""] = ""
    workers: int = Field(default=8, ge=0, le=128)
    pretrained: bool = True
    seed: int = Field(default=0, ge=0)
    deterministic: bool = True
    single_cls: bool = False
    rect: bool = False
    cos_lr: bool = False
    close_mosaic: int = Field(default=10, ge=0)
    amp: bool = True
    fraction: float = Field(default=1.0, gt=0.0, le=1.0)
    freeze: int | list[int] | None = None
    patience: int | None = Field(default=None, ge=0)
    teacher_checkpoint: str | None = Field(default=None)
    distillation_temperature: float | None = Field(default=None, gt=0.0)
    distillation_alpha: float | None = Field(default=None, ge=0.0, le=1.0)


class TrainStartInput(BaseModel):
    """Input for train_start tool."""

    dataset_path: Path
    model: str = "yolov8n.pt"
    epochs: int = Field(default=100, gt=0)
    batch: int = Field(default=16, gt=0)
    imgsz: int = Field(default=640, gt=0)
    device: str = "auto"
    task: Literal["detect", "segment", "classify", "pose", "obb"] = "detect"
    name: RunId | None = None
    force: bool = False
    max_concurrent_runs: int = Field(default=1, ge=0)
    tags: list[str] = Field(default_factory=list)
    options: TrainingOptions = Field(default_factory=lambda: TrainingOptions())
    extra_args: dict[str, Any] = Field(default_factory=dict)

    # Resource budgets
    max_runtime_seconds: int | None = Field(default=None, gt=0)
    max_disk_usage_gb: float | None = Field(default=None, gt=0.0)
    device_policy: Literal["any", "gpu_only", "cpu_only"] = "any"

    @model_validator(mode="before")
    @classmethod
    def merge_extra_args(cls, data: Any) -> Any:  # noqa: ANN401
        """Merge extra_args field values into options."""
        if isinstance(data, dict):
            extra_args = data.get("extra_args") or {}
            options = data.setdefault("options", {})
            for k, v in extra_args.items():
                options.setdefault(k, v)
        return data

    @field_validator("device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        """Validate device is cpu, cuda, or specific GPU index."""
        v_lower = v.strip().lower()
        if v_lower in ("auto", "cpu", "gpu", "cuda"):
            return v_lower
        if v_lower.startswith(("cuda:", "gpu:")):
            parts = v_lower.split(":")
            if len(parts) == 2 and parts[1].isdigit():
                return v_lower
        raise ValueError(
            "device must be 'auto', 'cpu', 'cuda', 'gpu', or specific index like 'cuda:0'"
        )

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Validate model source file extension format."""
        v = v.strip()
        if not v.endswith((".pt", ".yaml", ".yml")):
            raise ValueError("model source must end with .pt or .yaml/.yml")
        return v

    @model_validator(mode="after")
    def validate_device_policy(self) -> TrainStartInput:
        """Check compatibility between device and device_policy."""
        if self.device_policy == "gpu_only":
            if self.device == "cpu":
                raise ValueError("Device cannot be 'cpu' when device_policy is 'gpu_only'")
        elif self.device_policy == "cpu_only":
            if self.device not in ("cpu", "auto"):
                raise ValueError(
                    f"Device cannot be '{self.device}' when device_policy is 'cpu_only'"
                )
        return self


class TrainPreflightInput(BaseModel):
    """Input for train_preflight tool (shares validation with TrainStartInput)."""

    dataset_path: Path
    model: str = "yolov8n.pt"
    epochs: int = Field(default=100, gt=0)
    batch: int = Field(default=16, gt=0)
    imgsz: int = Field(default=640, gt=0)
    device: str = "auto"
    task: Literal["detect", "segment", "classify", "pose", "obb"] = "detect"
    name: RunId | None = None
    force: bool = False
    max_concurrent_runs: int = Field(default=1, ge=0)
    tags: list[str] = Field(default_factory=list)
    options: TrainingOptions = Field(default_factory=lambda: TrainingOptions())
    extra_args: dict[str, Any] = Field(default_factory=dict)

    # Resource budgets
    max_runtime_seconds: int | None = Field(default=None, gt=0)
    max_disk_usage_gb: float | None = Field(default=None, gt=0.0)
    device_policy: Literal["any", "gpu_only", "cpu_only"] = "any"

    @model_validator(mode="before")
    @classmethod
    def merge_extra_args(cls, data: Any) -> Any:  # noqa: ANN401
        """Merge extra_args field values into options."""
        if isinstance(data, dict):
            extra_args = data.get("extra_args") or {}
            options = data.setdefault("options", {})
            for k, v in extra_args.items():
                options.setdefault(k, v)
        return data

    @field_validator("device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        """Validate device via TrainStartInput."""
        return TrainStartInput.validate_device(v)

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Allow any model string for preflight diagnostics."""
        return v

    @model_validator(mode="after")
    def validate_device_policy(self) -> TrainPreflightInput:
        """Validate device policy via TrainStartInput rules."""
        if self.device_policy == "gpu_only":
            if self.device == "cpu":
                raise ValueError("Device cannot be 'cpu' when device_policy is 'gpu_only'")
        elif self.device_policy == "cpu_only":
            if self.device not in ("cpu", "auto"):
                raise ValueError(
                    f"Device cannot be '{self.device}' when device_policy is 'cpu_only'"
                )
        return self


class TrainPreflightOutput(BaseModel):
    """Output for train_preflight tool."""

    dataset_valid: bool
    dataset_classes_count: int
    dataset_path: str
    model_valid: bool
    model_source: str
    device_available: bool
    resolved_device: str
    disk_space_valid: bool
    available_disk_space_gb: float
    output_path_valid: bool
    resolved_run_dir: str
    concurrency_valid: bool
    active_runs_count: int
    warnings: list[str] = Field(default_factory=list)


class TrainStartOutput(BaseModel):
    """Output from train_start tool."""

    run_id: RunId
    status: str
    pid: int | None
    run_path: Path


class TrainStatusInput(BaseModel):
    """Input for train_status tool."""

    run_id: RunId


class TrainStatusOutput(BaseModel):
    """Output from train_status tool."""

    run_id: RunId
    status: str
    pid: int | None
    elapsed_seconds: float | None
    current_epoch: int | None
    best_map50: float | None
    run_path: Path


class TrainStopInput(BaseModel):
    """Input for train_stop tool."""

    run_id: RunId
    force: bool = False


class TrainStopOutput(BaseModel):
    """Output from train_stop tool."""

    run_id: str
    status: str
    message: str


class TrainResumeInput(BaseModel):
    """Input for train_resume tool."""

    run_id: RunId
    epochs: int | None = None


class TrainResumeOutput(BaseModel):
    """Output from train_resume tool."""

    run_id: str
    status: str
    pid: int | None
    run_path: Path

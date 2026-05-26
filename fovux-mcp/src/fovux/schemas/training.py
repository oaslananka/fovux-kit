"""Pydantic schemas for training tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from fovux.schemas.common import RunId


class TrainStartInput(BaseModel):
    """Input for train_start tool."""

    dataset_path: Path
    model: str = "yolov8n.pt"
    epochs: int = 100
    batch: int = 16
    imgsz: int = 640
    device: str = "auto"
    task: Literal["detect", "segment", "classify", "pose", "obb"] = "detect"
    name: RunId | None = None
    force: bool = False
    max_concurrent_runs: int = 1
    tags: list[str] = Field(default_factory=list)
    extra_args: dict[str, Any] = Field(default_factory=dict)


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

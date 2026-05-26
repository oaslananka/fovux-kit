"""Schemas for diagnostics, model profiling, and dataset quality tools."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class PackageHealth(BaseModel):
    """Status for an optional runtime dependency."""

    status: Literal["ok", "missing"]
    version: str | None = None
    detail: str = ""


class GpuHealth(BaseModel):
    """Best-effort accelerator detection summary."""

    available: bool
    accelerator: str
    device: str | None = None
    detail: str = ""
    cuda_version: str | None = None
    cudnn_version: str | None = None
    memory_free_gb: float | None = None
    memory_total_gb: float | None = None


class HttpHealth(BaseModel):
    """Health summary for the optional local HTTP transport."""

    reachable: bool
    base_url: str
    socket_path: Path | None = None
    socket_exists: bool = False
    detail: str = ""


class FovuxHomeHealth(BaseModel):
    """Filesystem summary for FOVUX_HOME."""

    path: Path
    writable: bool
    disk_free_gb: float
    disk_low: bool = False
    run_count: int
    model_count: int


class SystemSnapshot(BaseModel):
    """Best-effort local resource snapshot."""

    active_runs: int = 0
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    ram_total_gb: float = 0.0


class FovuxDoctorOutput(BaseModel):
    """Output from fovux_doctor."""

    python: str
    gpu: GpuHealth
    ultralytics: PackageHealth
    onnxruntime: PackageHealth
    onnx: PackageHealth
    fastmcp: PackageHealth
    http: HttpHealth
    fovux_home: FovuxHomeHealth
    system: SystemSnapshot = Field(default_factory=SystemSnapshot)
    license_notices: list[str] = Field(default_factory=list)
    requirements: dict[str, bool] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ModelProfileInput(BaseModel):
    """Input for model_profile."""

    checkpoint: str
    imgsz: int = 640
    device: str = "auto"


class ModelProfileOutput(BaseModel):
    """Output from model_profile."""

    checkpoint: str
    architecture: str
    parameters_millions: float
    gradients_millions: float
    gflops: float
    layers: int
    model_size_mb: float
    inference_memory_mb: float


class AnnotationQualityCheckInput(BaseModel):
    """Input for annotation_quality_check."""

    dataset_path: Path
    checks: list[str] = Field(default_factory=list)


class AnnotationIssue(BaseModel):
    """A dataset annotation issue."""

    check: str
    file: Path
    message: str


class AnnotationQualityCheckOutput(BaseModel):
    """Output from annotation_quality_check."""

    dataset_path: Path
    total_images: int
    total_issue_count: int
    issue_counts: dict[str, int] = Field(default_factory=dict)
    issues: list[AnnotationIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

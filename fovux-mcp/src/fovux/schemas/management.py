"""Pydantic schemas for model and run management tools."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from fovux.schemas.common import RunId


class ModelArtifact(BaseModel):
    """Metadata for a tracked model artifact."""

    name: str
    path: Path
    source: Literal["runs", "models"]
    format: str
    size_mb: float
    task: str | None = None
    run_id: str | None = None
    status: str | None = None
    modified_at: datetime | None = None


class ModelListOutput(BaseModel):
    """Output for model_list."""

    models: list[ModelArtifact] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 50


class ModelListInput(BaseModel):
    """Input for model_list."""

    offset: int = 0
    limit: int = 50


class RunMetricSummary(BaseModel):
    """Comparable run summary with experiment intelligence metrics."""

    run_id: str
    status: str
    model: str
    epochs: int
    current_epoch: int | None = None
    best_map50: float | None = None
    best_map50_95: float | None = None
    precision: float | None = None
    recall: float | None = None
    latency_ms: float | None = None
    model_size_mb: float | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    dataset_fingerprint: str | None = None
    export_target: str | None = None
    pareto_optimal: bool = False
    promotion_state: Literal["draft", "candidate", "approved", "deployed"] = "draft"
    run_path: Path


class RunCompareInput(BaseModel):
    """Input for run_compare."""

    run_ids: list[RunId] = Field(default_factory=list)
    output_path: Path | None = None


class RunCompareOutput(BaseModel):
    """Output for run_compare."""

    compared_runs: list[RunMetricSummary] = Field(default_factory=list)
    best_run_id: str | None = None
    report_path: Path
    chart_path: Path
    config_diffs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    pareto_frontier_run_ids: list[str] = Field(default_factory=list)
    model_cards: dict[str, str] = Field(default_factory=dict)
    suggested_next_experiment: str = ""


class RunDeleteInput(BaseModel):
    """Input for run_delete."""

    run_id: RunId
    delete_files: bool = True
    force: bool = False
    dry_run: bool = False


class RunDeleteOutput(BaseModel):
    """Output for run_delete."""

    run_id: str
    deleted_registry: bool
    deleted_files: bool
    dry_run: bool = False
    run_path: str | None = None
    affected_files_count: int = 0


class RunTagInput(BaseModel):
    """Input for run_tag."""

    run_id: RunId
    tags: list[str] = Field(default_factory=list)


class RunTagOutput(BaseModel):
    """Output for run_tag."""

    run_id: str
    tags: list[str]


class RunArchiveInput(BaseModel):
    """Input for run_archive."""

    run_id: RunId
    delete_original: bool = True
    dry_run: bool = False


class RunArchiveOutput(BaseModel):
    """Output from run_archive."""

    run_id: str
    archive_path: Path
    archived_files: int
    deleted_original: bool
    dry_run: bool = False


class DeploymentAdviseInput(BaseModel):
    """Input for deployment_advise."""

    model_path: str
    target_profile: Literal[
        "cpu_server",
        "nvidia_gpu_tensorrt",
        "jetson",
        "raspberry_pi",
        "android_tflite",
        "browser_wasm",
    ]
    dataset_path: str | None = None
    imgsz: int = 640


class DeploymentAdviseOutput(BaseModel):
    """Output for deployment_advise."""

    target_profile: str
    model_path: str
    format: str
    model_size_mb: float
    compatibility_preflight: dict[str, Any]
    quantization_recommendation: str
    readiness_score: int
    parity_check: dict[str, Any]
    benchmark_results: dict[str, Any]
    risk_warnings: list[str]
    runtime_snippets: dict[str, str]
    report_path: Path


class DemoInitInput(BaseModel):
    """Input for demo_init."""

    target_path: str


class DemoInitOutput(BaseModel):
    """Output for demo_init."""

    dataset_path: Path
    run_id: str
    run_path: Path
    model_path: Path
    export_path: Path

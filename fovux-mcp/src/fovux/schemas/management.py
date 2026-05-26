"""Pydantic schemas for model and run management tools."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

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
    """Comparable run summary."""

    run_id: str
    status: str
    model: str
    epochs: int
    current_epoch: int | None = None
    best_map50: float | None = None
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


class RunDeleteInput(BaseModel):
    """Input for run_delete."""

    run_id: RunId
    delete_files: bool = True
    force: bool = False


class RunDeleteOutput(BaseModel):
    """Output for run_delete."""

    run_id: str
    deleted_registry: bool
    deleted_files: bool


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


class RunArchiveOutput(BaseModel):
    """Output from run_archive."""

    run_id: str
    archive_path: Path
    archived_files: int
    deleted_original: bool

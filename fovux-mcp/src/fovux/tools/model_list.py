"""model_list — enumerate tracked checkpoints and exported artifacts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fovux.core.paths import FovuxPaths, ensure_fovux_dirs, get_fovux_home
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.schemas.management import ModelArtifact, ModelListInput, ModelListOutput
from fovux.server import mcp

_MODEL_EXTENSIONS = {".pt", ".onnx", ".tflite"}


@mcp.tool()
def model_list(offset: int = 0, limit: int = 50) -> dict[str, Any]:
    """List discovered models under ~/.fovux/models and run weight directories."""
    inp = ModelListInput(offset=offset, limit=limit)
    with tool_event("model_list", offset=offset, limit=limit):
        return _run_model_list(inp).model_dump(mode="json")


def _run_model_list(inp: ModelListInput | None = None) -> ModelListOutput:
    resolved_input = inp or ModelListInput()
    paths = ensure_fovux_dirs(get_fovux_home())
    registry = get_registry(paths.runs_db)
    records = {
        str(record.id): record
        for record in registry.list_runs(
            limit=max(resolved_input.limit * 4, 1),
            offset=max(resolved_input.offset, 0),
        )
    }

    models: list[ModelArtifact] = []
    models.extend(_collect_home_models(paths))
    models.extend(_collect_run_models(paths, records))
    models.sort(key=lambda item: item.modified_at or datetime.min, reverse=True)
    visible_models = models[resolved_input.offset : resolved_input.offset + resolved_input.limit]
    return ModelListOutput(
        models=visible_models,
        total=len(models),
        offset=resolved_input.offset,
        limit=resolved_input.limit,
    )


def _collect_home_models(paths: FovuxPaths) -> list[ModelArtifact]:
    artifacts: list[ModelArtifact] = []
    if not paths.models.exists():
        return artifacts

    for model_path in sorted(paths.models.iterdir()):
        if model_path.suffix.lower() not in _MODEL_EXTENSIONS or not model_path.is_file():
            continue
        stat = model_path.stat()
        artifacts.append(
            ModelArtifact(
                name=model_path.name,
                path=model_path,
                source="models",
                format=model_path.suffix.lower().lstrip("."),
                size_mb=stat.st_size / (1024 * 1024),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )
        )
    return artifacts


def _collect_run_models(paths: FovuxPaths, records: dict[str, Any]) -> list[ModelArtifact]:
    artifacts: list[ModelArtifact] = []
    if not paths.runs.exists():
        return artifacts

    for run_dir in sorted(paths.runs.iterdir()):
        if not run_dir.is_dir():
            continue
        record = records.get(run_dir.name)
        for model_path in _known_run_artifacts(run_dir):
            if model_path.suffix.lower() not in _MODEL_EXTENSIONS or not model_path.is_file():
                continue
            stat = model_path.stat()
            artifacts.append(
                ModelArtifact(
                    name=model_path.name,
                    path=model_path,
                    source="runs",
                    format=model_path.suffix.lower().lstrip("."),
                    size_mb=stat.st_size / (1024 * 1024),
                    task=getattr(record, "task", None),
                    run_id=run_dir.name,
                    status=str(getattr(record, "status", "")) or None,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                )
            )
    return artifacts


def _known_run_artifacts(run_dir: Path) -> list[Path]:
    """Return model artifact candidates without recursively walking whole run trees."""
    candidates: list[Path] = []
    for directory in (run_dir, run_dir / "weights", run_dir / "exports"):
        if not directory.exists():
            continue
        for extension in _MODEL_EXTENSIONS:
            candidates.extend(directory.glob(f"*{extension}"))
    return sorted({path.resolve(strict=False) for path in candidates})

"""train_preflight — perform verification and resource checks before training starts."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from fovux.core.dataset_config import validate_yolo_data_yaml
from fovux.core.paths import FovuxPaths, get_fovux_home
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.core.validation import ensure_within_root, validate_run_id
from fovux.schemas.training import TrainingOptions, TrainPreflightInput, TrainPreflightOutput
from fovux.server import mcp


@mcp.tool()
def train_preflight(
    dataset_path: str,
    model: str = "yolov8n.pt",
    epochs: int = 100,
    batch: int = 16,
    imgsz: int = 640,
    device: str = "auto",
    task: str = "detect",
    name: str | None = None,
    force: bool = False,
    max_concurrent_runs: int = 1,
    tags: list[str] | None = None,
    options: dict[str, Any] | None = None,
    max_runtime_seconds: int | None = None,
    max_disk_usage_gb: float | None = None,
    device_policy: str = "any",
) -> dict[str, Any]:
    """Perform preflight checks and return a diagnostic training compatibility summary."""
    inp = TrainPreflightInput(
        dataset_path=Path(dataset_path),
        model=model,
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device,
        task=task,  # type: ignore[arg-type]
        name=name,
        force=force,
        max_concurrent_runs=max_concurrent_runs,
        tags=tags or [],
        options=TrainingOptions(**(options or {})),
        max_runtime_seconds=max_runtime_seconds,
        max_disk_usage_gb=max_disk_usage_gb,
        device_policy=device_policy,  # type: ignore[arg-type]
    )
    with tool_event(
        "train_preflight",
        dataset_path=dataset_path,
        model=model,
        requested_run_id=name,
    ):
        return _run_train_preflight(inp).model_dump(mode="json")


def _run_train_preflight(inp: TrainPreflightInput) -> TrainPreflightOutput:
    warnings: list[str] = []

    # 1. Dataset Check
    dataset_path = inp.dataset_path.expanduser().resolve()
    dataset_valid = False
    dataset_classes_count = 0
    if not dataset_path.exists():
        warnings.append(f"Dataset path does not exist: {dataset_path}")
    else:
        try:
            data = validate_yolo_data_yaml(dataset_path)
            dataset_valid = True
            nc = data.get("nc")
            if nc is not None:
                dataset_classes_count = int(nc)
            else:
                names = data.get("names")
                if isinstance(names, list):
                    dataset_classes_count = len(names)
                elif isinstance(names, dict):
                    dataset_classes_count = len(names)
        except Exception as exc:
            warnings.append(f"Dataset YAML format invalid: {exc}")

    # 2. Model Check
    model_valid = True
    model_source = inp.model
    if not (inp.model.endswith(".pt") or inp.model.endswith(".yaml") or inp.model.endswith(".yml")):
        model_valid = False
        warnings.append("Model name/path must end with .pt or .yaml/.yml")

    # 3. Device Check
    device_available = True
    resolved_device = "cpu"
    device_lower = inp.device.lower().strip()

    try:
        import torch  # type: ignore[import-not-found]

        has_cuda = torch.cuda.is_available()
    except ImportError:
        has_cuda = shutil.which("nvidia-smi") is not None
        warnings.append("PyTorch (torch) is not installed. Training will fail.")

    if device_lower == "cpu":
        resolved_device = "cpu"
    elif device_lower in ("cuda", "gpu", "auto") or device_lower.startswith(("cuda:", "gpu:")):
        if has_cuda:
            resolved_device = (
                "cuda:0"
                if device_lower in ("cuda", "gpu", "auto")
                else device_lower.replace("gpu", "cuda")
            )
        else:
            resolved_device = "cpu"
            if device_lower != "auto":
                device_available = False
                warnings.append(
                    f"GPU device '{inp.device}' requested but CUDA/GPU is not available."
                )

    # 4. Disk Space Check
    paths = FovuxPaths(get_fovux_home())
    runs_root = paths.runs
    runs_root.mkdir(parents=True, exist_ok=True)
    try:
        usage = shutil.disk_usage(runs_root)
        free_gb = usage.free / (1024**3)
    except Exception:
        free_gb = 0.0

    disk_space_valid = True
    if inp.max_disk_usage_gb is not None:
        if free_gb < inp.max_disk_usage_gb:
            disk_space_valid = False
            warnings.append(
                f"Available disk space ({free_gb:.2f} GB) is less than "
                f"maximum required ({inp.max_disk_usage_gb:.2f} GB)."
            )
    elif free_gb < 1.0:
        disk_space_valid = False
        warnings.append(f"Available disk space is critically low: {free_gb:.2f} GB.")

    # 5. Output Path Check
    run_id = validate_run_id(inp.name or f"run_{uuid.uuid4().hex[:8]}")
    run_dir = ensure_within_root(paths.runs / run_id, paths.runs)
    output_path_valid = True
    if run_dir.exists() and not inp.force:
        output_path_valid = False
        warnings.append(f"Output directory already exists: {run_dir}. Use force=True to overwrite.")

    # 6. Concurrency Check
    registry = get_registry(paths.runs_db)
    active_runs = registry.list_runs(status="running", limit=10_000)
    pending_runs = registry.list_runs(status="pending", limit=10_000)
    active_count = len(active_runs) + len(pending_runs)
    concurrency_valid = True
    if inp.max_concurrent_runs > 0 and active_count >= inp.max_concurrent_runs:
        concurrency_valid = False
        warnings.append(f"Active runs limit reached ({active_count}/{inp.max_concurrent_runs}).")

    return TrainPreflightOutput(
        dataset_valid=dataset_valid,
        dataset_classes_count=dataset_classes_count,
        dataset_path=str(dataset_path),
        model_valid=model_valid,
        model_source=model_source,
        device_available=device_available,
        resolved_device=resolved_device,
        disk_space_valid=disk_space_valid,
        available_disk_space_gb=round(free_gb, 3),
        output_path_valid=output_path_valid,
        resolved_run_dir=str(run_dir),
        concurrency_valid=concurrency_valid,
        active_runs_count=active_count,
        warnings=warnings,
    )

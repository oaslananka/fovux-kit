"""sync_to_mlflow — optional MLflow export for local run metadata."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from fovux.core.checkpoints import load_metrics_jsonl
from fovux.core.errors import FovuxError, FovuxTrainingRunNotFoundError
from fovux.core.paths import ensure_fovux_dirs
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.schemas.inference import SyncToMlflowOutput
from fovux.server import mcp


@mcp.tool()
def sync_to_mlflow(
    run_id: str,
    mlflow_tracking_uri: str = "http://localhost:5000",
) -> dict[str, Any]:
    """Sync one Fovux run's params and metrics to an optional MLflow server."""
    with tool_event("sync_to_mlflow", run_id=run_id):
        return _run_sync_to_mlflow(run_id, mlflow_tracking_uri).model_dump(mode="json")


def _run_sync_to_mlflow(run_id: str, mlflow_tracking_uri: str) -> SyncToMlflowOutput:
    try:
        mlflow = importlib.import_module("mlflow")
    except ImportError as exc:
        raise FovuxError(
            "MLflow integration requires the optional 'mlflow' package.",
            hint="Install mlflow in the active environment or skip this optional sync.",
        ) from exc

    registry = get_registry(ensure_fovux_dirs().runs_db)
    record = registry.get_run(run_id)
    if record is None:
        raise FovuxTrainingRunNotFoundError(run_id)
    run_dir = Path(record.run_path)
    params_path = run_dir / "params.json"
    params = json.loads(params_path.read_text(encoding="utf-8")) if params_path.exists() else {}
    metrics = load_metrics_jsonl(run_dir)

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    with mlflow.start_run(run_name=run_id):
        for key, value in params.items():
            mlflow.log_param(key, value)
        for row in metrics:
            step = int(row.get("epoch", 0))
            metric_values = row.get("metrics", {})
            if isinstance(metric_values, dict):
                for key, value in metric_values.items():
                    if isinstance(value, (int, float)):
                        mlflow.log_metric(str(key), float(value), step=step)

    return SyncToMlflowOutput(
        run_id=run_id,
        tracking_uri=mlflow_tracking_uri,
        metrics_logged=sum(
            len(row.get("metrics", {})) for row in metrics if isinstance(row.get("metrics"), dict)
        ),
        params_logged=len(params),
    )

"""train_adjust — persist live training adjustment requests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fovux.core.errors import FovuxTrainingRunNotFoundError
from fovux.core.json_io import write_json_atomically
from fovux.core.paths import ensure_fovux_dirs
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.schemas.inference import TrainAdjustInput, TrainAdjustOutput
from fovux.server import mcp


@mcp.tool()
def train_adjust(
    run_id: str,
    learning_rate: float | None = None,
    mosaic: bool | None = None,
) -> dict[str, Any]:
    """Write a control request for a running training worker."""
    inp = TrainAdjustInput(run_id=run_id, learning_rate=learning_rate, mosaic=mosaic)
    with tool_event("train_adjust", run_id=run_id):
        return _run_train_adjust(inp).model_dump(mode="json")


def _run_train_adjust(inp: TrainAdjustInput) -> TrainAdjustOutput:
    registry = get_registry(ensure_fovux_dirs().runs_db)
    record = registry.get_run(inp.run_id)
    if record is None:
        raise FovuxTrainingRunNotFoundError(inp.run_id)

    applied: dict[str, object] = {}
    if inp.learning_rate is not None:
        applied["learning_rate"] = inp.learning_rate
    if inp.mosaic is not None:
        applied["mosaic"] = inp.mosaic
    applied["updated_at"] = datetime.now(UTC).isoformat()

    control_path = Path(record.run_path) / "control.json"
    write_json_atomically(control_path, applied)
    return TrainAdjustOutput(run_id=inp.run_id, control_path=control_path, applied=applied)

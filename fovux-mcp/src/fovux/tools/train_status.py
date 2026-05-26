"""train_status — query the status of a running or finished training run."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from fovux.core.checkpoints import (
    read_metrics_summary,
)
from fovux.core.errors import FovuxTrainingRunNotFoundError
from fovux.core.paths import FovuxPaths, get_fovux_home
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.schemas.training import TrainStatusInput, TrainStatusOutput
from fovux.server import mcp


@mcp.tool()
def train_status(run_id: str) -> dict[str, Any]:
    """Return the current status and latest metrics for a training run."""
    inp = TrainStatusInput(run_id=run_id)
    with tool_event("train_status", run_id=run_id):
        return _run_train_status(inp).model_dump(mode="json")


def _run_train_status(inp: TrainStatusInput) -> TrainStatusOutput:
    paths = FovuxPaths(get_fovux_home())
    registry = get_registry(paths.runs_db)

    record = registry.get_run(inp.run_id)
    if record is None:
        raise FovuxTrainingRunNotFoundError(inp.run_id)

    run_dir = Path(record.run_path)

    status = str(record.status)
    if status == "running" and record.pid is not None:
        if not _pid_alive(int(record.pid)):
            worker_status = _read_worker_status(run_dir)
            status = worker_status or "complete"
            registry.update_status(inp.run_id, status)  # type: ignore[arg-type]

    elapsed = _elapsed(record)
    current_epoch, best_map50 = _read_metrics(run_dir)

    return TrainStatusOutput(
        run_id=inp.run_id,
        status=status,
        pid=int(record.pid) if record.pid is not None else None,
        elapsed_seconds=elapsed,
        current_epoch=current_epoch,
        best_map50=best_map50,
        run_path=run_dir,
    )


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        tasklist = shutil.which("tasklist.exe") or shutil.which("tasklist")
        if tasklist is None:
            return False
        try:
            result = subprocess.run(  # noqa: S603 - fixed Windows system utility only
                [tasklist, "/FI", f"PID eq {pid}"],
                capture_output=True,
                check=False,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _read_worker_status(run_dir: Path) -> str | None:
    status_file = run_dir / "status.json"
    if status_file.exists():
        try:
            data = cast(dict[str, object], json.loads(status_file.read_text()))
            status = data.get("status")
            return str(status) if status is not None else None
        except (json.JSONDecodeError, OSError, TypeError):
            return None
    return None


def _elapsed(record: object) -> float | None:
    started = cast(datetime | None, getattr(record, "started_at", None))
    if started is None:
        return None
    finished = cast(datetime | None, getattr(record, "finished_at", None))
    end = finished or datetime.now(tz=UTC).replace(tzinfo=None)
    delta = end - started
    return delta.total_seconds()


def _read_metrics(run_dir: Path) -> tuple[int | None, float | None]:
    return read_metrics_summary(run_dir)

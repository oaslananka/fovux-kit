"""train_stop — terminate a running training subprocess."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fovux.core.errors import FovuxPathValidationError, FovuxTrainingRunNotFoundError
from fovux.core.paths import FovuxPaths, get_fovux_home
from fovux.core.processes import load_process_identity, terminate_process_tree
from fovux.core.runs import RunRegistry, get_registry
from fovux.core.tooling import tool_event
from fovux.core.validation import ensure_within_root
from fovux.schemas.training import TrainStopInput, TrainStopOutput
from fovux.server import mcp


@mcp.tool()
def train_stop(run_id: str, force: bool = False) -> dict[str, Any]:
    """Stop a running training run by sending a termination signal to its subprocess."""
    inp = TrainStopInput(run_id=run_id, force=force)
    with tool_event("train_stop", run_id=run_id, force=force):
        return _run_train_stop(inp).model_dump(mode="json")


def _run_train_stop(inp: TrainStopInput) -> TrainStopOutput:
    paths = FovuxPaths(get_fovux_home())
    registry = get_registry(paths.runs_db)

    record = registry.get_run(inp.run_id)
    if record is None:
        raise FovuxTrainingRunNotFoundError(inp.run_id)

    status = str(record.status)
    if status != "running":
        return TrainStopOutput(
            run_id=inp.run_id,
            status=status,
            message=f"Run is not running (status={status}). Nothing to stop.",
        )

    pid = int(record.pid) if record.pid is not None else None
    message = "No PID recorded — status updated without signalling."

    if pid is not None:
        try:
            run_dir = ensure_within_root(Path(record.run_path), paths.runs)
        except FovuxPathValidationError:
            return _refuse_missing_process_identity(registry, inp.run_id, status)
        identity = load_process_identity(run_dir, pid)
        if identity is None:
            return _refuse_missing_process_identity(registry, inp.run_id, status)
        result = terminate_process_tree(identity, force=inp.force)
        message = result.message
        if result.status == "mismatch":
            registry.update_extra(
                inp.run_id,
                {
                    "process_stop_status": result.status,
                    "process_signal_sent": result.signal_sent,
                    "process_stale": True,
                    "stop_failure_class": "process_identity_mismatch",
                },
            )
            return TrainStopOutput(run_id=inp.run_id, status=status, message=message)
        if result.status in {"permission_denied", "failed"}:
            registry.update_extra(
                inp.run_id,
                {
                    "process_stop_status": result.status,
                    "process_signal_sent": result.signal_sent,
                    "process_stale": True,
                    "stop_failure_class": f"process_signal_{result.status}",
                },
            )
            return TrainStopOutput(run_id=inp.run_id, status=status, message=message)
        registry.update_extra(
            inp.run_id,
            {
                "process_stop_status": result.status,
                "process_signal_sent": result.signal_sent,
                "process_stale": result.status == "missing",
                "stop_failure_class": "missing_process" if result.status == "missing" else None,
            },
        )

    registry.update_status(inp.run_id, "stopped")
    return TrainStopOutput(run_id=inp.run_id, status="stopped", message=message)


def _refuse_missing_process_identity(
    registry: RunRegistry,
    run_id: str,
    status: str,
) -> TrainStopOutput:
    registry.update_extra(
        run_id,
        {
            "process_stop_status": "refused",
            "process_signal_sent": False,
            "process_stale": True,
            "stop_failure_class": "missing_process_identity",
        },
    )
    return TrainStopOutput(
        run_id=run_id,
        status=status,
        message=(
            "Recorded process identity is missing or incomplete; "
            "refusing to signal a PID by number alone."
        ),
    )


def _kill_pid(pid: int, *, force: bool) -> str:
    try:
        if sys.platform == "win32":
            flag = "/F" if force else ""
            args = ["taskkill", "/PID", str(pid)]
            if flag:
                args.append(flag)
            subprocess.run(args, capture_output=True, check=False)  # noqa: S603
        else:
            import signal as _signal

            sig = getattr(_signal, "SIGKILL", _signal.SIGTERM) if force else _signal.SIGTERM
            os.kill(pid, sig)
        return f"Signal sent to PID {pid}."
    except (ProcessLookupError, OSError):
        return f"PID {pid} no longer exists."

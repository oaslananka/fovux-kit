"""train_resume — resume a stopped or failed training run."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from fovux.core.errors import FovuxTrainingRunNotFoundError, FovuxTrainingSubprocessError
from fovux.core.json_io import write_json_atomically
from fovux.core.paths import FovuxPaths, get_fovux_home
from fovux.core.processes import (
    ProcessIdentity,
    capture_process_identity,
    process_identity_payload,
    terminate_process_tree,
)
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.core.validation import ensure_within_root
from fovux.schemas.training import TrainResumeInput, TrainResumeOutput
from fovux.server import mcp


@mcp.tool()
def train_resume(run_id: str, epochs: int | None = None) -> dict[str, Any]:
    """Resume a stopped or failed training run from its last checkpoint."""
    inp = TrainResumeInput(run_id=run_id, epochs=epochs)
    with tool_event("train_resume", run_id=run_id, epochs=epochs):
        return _run_train_resume(inp).model_dump(mode="json")


def _run_train_resume(inp: TrainResumeInput) -> TrainResumeOutput:
    paths = FovuxPaths(get_fovux_home())
    registry = get_registry(paths.runs_db)

    record = registry.get_run(inp.run_id)
    if record is None:
        raise FovuxTrainingRunNotFoundError(inp.run_id)

    run_dir = ensure_within_root(Path(record.run_path), paths.runs)
    params_path = run_dir / "params.json"
    params = (
        cast(dict[str, Any], json.loads(params_path.read_text())) if params_path.exists() else {}
    )

    last_pt = run_dir / "weights" / "last.pt"
    if not last_pt.exists():
        last_pt = run_dir / "last.pt"

    params["resume_checkpoint"] = str(last_pt) if last_pt.exists() else None
    if inp.epochs is not None:
        params["epochs"] = inp.epochs

    write_json_atomically(params_path, params)

    command = [sys.executable, "-m", "fovux.core.train_worker", str(run_dir)]
    popen_kwargs: dict[str, Any] = {
        "stdout": None,
        "stderr": None,
        "close_fds": True,
        "env": {**os.environ, "FOVUX_RUN_DIR": str(run_dir)},
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    try:
        with (
            (run_dir / "stdout.log").open("a", encoding="utf-8") as stdout_fh,
            (run_dir / "stderr.log").open("a", encoding="utf-8") as stderr_fh,
        ):
            popen_kwargs["stdout"] = stdout_fh
            popen_kwargs["stderr"] = stderr_fh
            proc = subprocess.Popen(  # noqa: S603 - fixed local module execution only
                command,
                **popen_kwargs,
            )
    except OSError as exc:
        registry.update_status(inp.run_id, "failed")
        raise FovuxTrainingSubprocessError(str(exc)) from exc

    identity: ProcessIdentity | None = None
    cleanup_failure: str | None = None
    try:
        identity = capture_process_identity(pid=proc.pid, command=command, cwd=Path.cwd())
        write_json_atomically(
            run_dir / "pid.txt",
            {"pid": proc.pid, "process": process_identity_payload(identity)},
        )
        registry.update_status(inp.run_id, "running", pid=proc.pid)
    except Exception as exc:
        if identity is not None:
            try:
                result = terminate_process_tree(identity, force=True)
            except Exception as term_exc:
                cleanup_failure = str(term_exc)
            else:
                if result.status not in {"terminated", "missing"}:
                    cleanup_failure = result.message
            if cleanup_failure and proc.poll() is None:
                with suppress(OSError):
                    proc.terminate()
        elif proc.poll() is None:
            with suppress(OSError):
                proc.terminate()
        with suppress(Exception):
            registry.update_status(inp.run_id, "failed", pid=proc.pid)
        message = str(exc)
        if cleanup_failure:
            message = f"{message}; cleanup failed: {cleanup_failure}"
        raise FovuxTrainingSubprocessError(message) from exc

    return TrainResumeOutput(
        run_id=inp.run_id,
        status="running",
        pid=proc.pid,
        run_path=run_dir,
    )

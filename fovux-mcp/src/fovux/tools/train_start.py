"""train_start — launch a non-blocking YOLO training subprocess."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

from fovux.core.dataset_config import validate_yolo_data_yaml
from fovux.core.errors import (
    FovuxDatasetNotFoundError,
    FovuxTrainingAlreadyRunningError,
    FovuxTrainingSubprocessError,
)
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
from fovux.core.validation import ensure_within_root, validate_run_id
from fovux.schemas.training import TrainStartInput, TrainStartOutput
from fovux.server import mcp


@mcp.tool()
def train_start(
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
    extra_args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Launch a YOLO training run as a non-blocking background subprocess.

    Returns immediately with a run_id for monitoring via train_status.
    """
    inp = TrainStartInput(
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
        extra_args=extra_args or {},
    )
    with tool_event(
        "train_start",
        dataset_path=dataset_path,
        model=model,
        requested_run_id=name,
        force=force,
        max_concurrent_runs=max_concurrent_runs,
    ) as logger:
        output = _run_train_start(inp)
        logger.info("train_start_spawned", run_id=output.run_id, pid=output.pid)
        return output.model_dump(mode="json")


def _run_train_start(inp: TrainStartInput) -> TrainStartOutput:
    dataset_path = inp.dataset_path.expanduser().resolve()
    if not dataset_path.exists():
        raise FovuxDatasetNotFoundError(str(dataset_path))
    validate_yolo_data_yaml(dataset_path)

    paths = FovuxPaths(get_fovux_home())
    registry = get_registry(paths.runs_db)

    run_id = validate_run_id(inp.name or f"run_{uuid.uuid4().hex[:8]}")
    run_dir = ensure_within_root(paths.runs / run_id, paths.runs)

    existing = registry.get_run(run_id)
    if existing is not None:
        existing_status = str(existing.status)
        if existing_status == "running":
            raise FovuxTrainingAlreadyRunningError(
                f"Run '{run_id}' is already running. Stop it before starting a new run."
            )
        if not inp.force:
            raise FovuxTrainingAlreadyRunningError(
                f"Run '{run_id}' already exists with status '{existing_status}'. "
                "Use a different name or pass force=True to overwrite."
            )

    if inp.max_concurrent_runs > 0:
        active_count = len(registry.list_runs(status="running", limit=10_000))
        if active_count >= inp.max_concurrent_runs:
            raise FovuxTrainingAlreadyRunningError(
                f"Cannot start run '{run_id}': {active_count} concurrent training run(s) "
                f"already active and max_concurrent_runs={inp.max_concurrent_runs}."
            )

    if existing is not None and inp.force:
        shutil.rmtree(run_dir, ignore_errors=True)
        registry.delete_run(run_id)

    run_dir.mkdir(parents=True, exist_ok=True)

    params: dict[str, Any] = {
        "model": inp.model,
        "dataset_path": str(dataset_path),
        "epochs": inp.epochs,
        "batch": inp.batch,
        "imgsz": inp.imgsz,
        "device": inp.device,
        "task": inp.task,
        "extra_args": inp.extra_args,
    }
    write_json_atomically(run_dir / "params.json", params)

    registry.create_run(
        run_id=run_id,
        run_path=run_dir,
        model=inp.model,
        dataset_path=dataset_path,
        task=inp.task,
        epochs=inp.epochs,
        tags=inp.tags,
    )

    stdout_log = run_dir / "stdout.log"
    stderr_log = run_dir / "stderr.log"
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
            stdout_log.open("w", encoding="utf-8") as stdout_fh,
            stderr_log.open("w", encoding="utf-8") as stderr_fh,
        ):
            popen_kwargs["stdout"] = stdout_fh
            popen_kwargs["stderr"] = stderr_fh
            proc = subprocess.Popen(  # noqa: S603 - fixed local module execution only
                command,
                **popen_kwargs,
            )
    except OSError as exc:
        registry.update_status(run_id, "failed")
        raise FovuxTrainingSubprocessError(str(exc)) from exc

    identity: ProcessIdentity | None = None
    cleanup_failure: str | None = None
    try:
        identity = capture_process_identity(pid=proc.pid, command=command, cwd=Path.cwd())
        write_json_atomically(
            run_dir / "pid.txt",
            {"pid": proc.pid, "process": process_identity_payload(identity)},
        )
        registry.update_status(run_id, "running", pid=proc.pid)
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
            registry.update_status(run_id, "failed", pid=proc.pid)
        message = str(exc)
        if cleanup_failure:
            message = f"{message}; cleanup failed: {cleanup_failure}"
        raise FovuxTrainingSubprocessError(message) from exc

    return TrainStartOutput(
        run_id=run_id,
        status="running",
        pid=proc.pid,
        run_path=run_dir,
    )

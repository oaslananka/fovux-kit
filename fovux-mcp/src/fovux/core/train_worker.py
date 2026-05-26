"""Standalone training worker — launched as a subprocess by train_start.

Usage: python -m fovux.core.train_worker <run_dir>

Reads params.json from <run_dir>, runs YOLO training, and writes
status.json updates so train_status can poll progress.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fovux.core.checkpoints import read_metric_rows
from fovux.core.logging import configure_logging, get_logger
from fovux.core.paths import FovuxPaths, get_fovux_home
from fovux.core.runs import get_registry
from fovux.core.ultralytics_adapter import YoloModel

logger = get_logger(__name__)
_STOP_REQUESTED = False
_CURRENT_RUN_DIR: Path | None = None


def load_yolo_model(model: str) -> YoloModel:
    """Lazy-load Ultralytics only after the subprocess is ready to train."""
    from fovux.core.ultralytics_adapter import load_yolo_model as adapter_load_yolo_model

    return adapter_load_yolo_model(model)


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat()


def _write_status(status_path: Path, status: str, **extra: object) -> None:
    data = {"status": status, "updated_at": _utcnow(), **extra}
    status_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _handle_stop_signal(signum: int, frame: object | None) -> None:
    del frame
    global _STOP_REQUESTED
    _STOP_REQUESTED = True
    logger.warning("train_worker_stop_requested", signal=signum)
    run_dir = _CURRENT_RUN_DIR or _run_dir_from_env()
    if run_dir is not None:
        _write_status(run_dir / "status.json", "stopped", pid=os.getpid(), signal=signum)
        _update_registry_status(run_dir, "stopped")
    sys.exit(0)


def run(run_dir: Path) -> None:
    """Execute one detached training run and keep its status file up to date."""
    global _CURRENT_RUN_DIR, _STOP_REQUESTED
    _STOP_REQUESTED = False
    _CURRENT_RUN_DIR = run_dir
    params_path = run_dir / "params.json"
    status_path = run_dir / "status.json"
    metrics_path = run_dir / "metrics.jsonl"

    params: dict[str, Any] = json.loads(params_path.read_text())
    logger.info("train_worker_start", run_dir=str(run_dir), model=params.get("model"))
    _write_status(status_path, "running", pid=os.getpid())

    signal.signal(signal.SIGTERM, _handle_stop_signal)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _handle_stop_signal)

    stop_event = threading.Event()
    mirror_thread = threading.Thread(
        target=_mirror_metrics_csv,
        args=(run_dir, metrics_path, stop_event),
        daemon=True,
    )
    mirror_thread.start()

    try:
        model_source = params.get("resume_checkpoint") or params["model"]
        model = load_yolo_model(str(model_source))
        train_kwargs: dict[str, Any] = {
            "data": params["dataset_path"],
            "epochs": params["epochs"],
            "batch": params["batch"],
            "imgsz": params["imgsz"],
            "device": params["device"],
            "task": params["task"],
            "project": str(run_dir),
            "name": "weights",
            "exist_ok": True,
        }
        train_kwargs.update(params.get("extra_args", {}))
        if params.get("resume_checkpoint"):
            train_kwargs["resume"] = True

        model.train(**train_kwargs)
        stop_event.set()
        mirror_thread.join(timeout=2.0)
        final_status = "stopped" if _STOP_REQUESTED else "complete"
        _write_status(status_path, final_status, pid=os.getpid())
        _update_registry_status(run_dir, final_status)
        logger.info("train_worker_complete", run_dir=str(run_dir), status=final_status)
    except KeyboardInterrupt:
        stop_event.set()
        mirror_thread.join(timeout=2.0)
        _write_status(status_path, "stopped", pid=os.getpid())
        _update_registry_status(run_dir, "stopped")
        logger.warning("train_worker_stopped", run_dir=str(run_dir))
        sys.exit(0)
    except SystemExit:
        stop_event.set()
        mirror_thread.join(timeout=2.0)
        raise
    except Exception:
        stop_event.set()
        mirror_thread.join(timeout=2.0)
        _write_status(status_path, "failed", pid=os.getpid(), error=traceback.format_exc())
        _update_registry_status(run_dir, "failed")
        logger.error("train_worker_failed", run_dir=str(run_dir), traceback=traceback.format_exc())
        sys.exit(1)
    finally:
        _CURRENT_RUN_DIR = None


def _run_dir_from_env() -> Path | None:
    raw = os.environ.get("FOVUX_RUN_DIR")
    return Path(raw) if raw else None


def _update_registry_status(run_dir: Path, status: str) -> None:
    try:
        registry = get_registry(FovuxPaths(get_fovux_home()).runs_db)
        registry.update_status(run_dir.name, status)  # type: ignore[arg-type]
    except Exception as exc:
        logger.warning(
            "train_worker_registry_update_failed",
            run_dir=str(run_dir),
            status=status,
            error=str(exc),
        )


def _mirror_metrics_csv(run_dir: Path, metrics_path: Path, stop_event: threading.Event) -> None:
    seen_epochs: set[int] = set()
    while not stop_event.is_set():
        rows = read_metric_rows(run_dir)
        if rows:
            _append_metric_rows(run_dir, metrics_path, rows, seen_epochs)
        stop_event.wait(0.25)


def _append_metric_rows(
    run_dir: Path,
    metrics_path: Path,
    rows: list[dict[str, str]],
    seen_epochs: set[int],
) -> None:
    lines: list[str] = []
    for row in rows:
        epoch_raw = row.get("epoch")
        if epoch_raw is None:
            continue
        epoch = int(float(epoch_raw)) + 1
        if epoch in seen_epochs:
            continue
        seen_epochs.add(epoch)
        metrics: dict[str, float] = {}
        for key, value in row.items():
            if key == "epoch" or value in (None, ""):
                continue
            try:
                metrics[key] = float(value)
            except ValueError:
                continue
        lines.append(
            json.dumps(
                {
                    "run_id": run_dir.name,
                    "epoch": epoch,
                    "wall_time_s": 0.0,
                    "metrics": metrics,
                    "eta_s": 0.0,
                }
            )
        )
    if lines:
        with metrics_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    configure_logging()
    if len(sys.argv) < 2:
        logger.error(
            "train_worker_usage_error",
            message="Usage: python -m fovux.core.train_worker <run_dir>",
        )
        sys.exit(1)
    run(Path(sys.argv[1]))

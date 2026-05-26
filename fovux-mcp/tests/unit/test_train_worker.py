"""Tests for the detached training worker module."""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fovux.core.runs import RunRegistry
from fovux.core.train_worker import _handle_stop_signal, _write_status, run

TRAIN_WORKER_RUNPY_WARNING = (
    "ignore:'fovux.core.train_worker' found in sys.modules after import of package "
    "'fovux.core', but prior to execution of 'fovux.core.train_worker'; this may "
    "result in unpredictable behaviour:RuntimeWarning:runpy"
)


def _write_params(run_dir: Path, **overrides: object) -> dict[str, object]:
    params: dict[str, object] = {
        "model": "yolov8n.pt",
        "dataset_path": str(run_dir / "dataset"),
        "epochs": 2,
        "batch": 4,
        "imgsz": 64,
        "device": "cpu",
        "task": "detect",
        "pid": 1234,
        "extra_args": {"patience": 5},
    }
    params.update(overrides)
    (run_dir / "params.json").write_text(json.dumps(params))
    return params


def test_write_status_persists_extra_fields(tmp_path: Path) -> None:
    """Status writes should include the requested state and additional metadata."""
    status_path = tmp_path / "status.json"

    _write_status(status_path, "running", pid=77)

    payload = json.loads(status_path.read_text())
    assert payload["status"] == "running"
    assert payload["pid"] == 77
    assert "updated_at" in payload


def test_stop_signal_marks_registry_stopped(tmp_path: Path, monkeypatch) -> None:
    """SIGTERM/SIGINT handling should update both status.json and the registry."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    run_dir = tmp_path / "runs" / "signal_run"
    monkeypatch.setenv("FOVUX_RUN_DIR", str(run_dir))
    run_dir.mkdir(parents=True)
    registry = RunRegistry(tmp_path / "runs.db")
    registry.create_run(
        run_id="signal_run",
        run_path=run_dir,
        model="yolov8n.pt",
        dataset_path=tmp_path / "dataset",
        task="detect",
        epochs=1,
    )
    registry.update_status("signal_run", "running", pid=123)

    with pytest.raises(SystemExit) as exc_info:
        _handle_stop_signal(15, None)

    assert exc_info.value.code == 0
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "stopped"
    assert registry.get_run("signal_run").status == "stopped"  # type: ignore[union-attr]


def test_run_marks_training_complete(tmp_path: Path) -> None:
    """A successful worker run should finish with a complete status file."""
    run_dir = tmp_path / "run_success"
    run_dir.mkdir()
    _write_params(run_dir)
    fake_model = MagicMock()

    with patch("fovux.core.train_worker.load_yolo_model", return_value=fake_model):
        run(run_dir)

    status = json.loads((run_dir / "status.json").read_text())
    assert status["status"] == "complete"
    assert fake_model.train.call_args.kwargs["data"] == str(run_dir / "dataset")
    assert fake_model.train.call_args.kwargs["project"] == str(run_dir)


def test_run_uses_resume_checkpoint_with_user_dataset(tmp_path: Path) -> None:
    """Resume mode should load the checkpoint and preserve user dataset configuration."""
    run_dir = tmp_path / "run_resume"
    weights_dir = run_dir / "weights"
    weights_dir.mkdir(parents=True)
    last_checkpoint = weights_dir / "last.pt"
    last_checkpoint.write_bytes(b"checkpoint")
    _write_params(run_dir, resume_checkpoint=str(last_checkpoint))

    resumed_model = MagicMock()
    with patch(
        "fovux.core.train_worker.load_yolo_model",
        return_value=resumed_model,
    ) as loader:
        run(run_dir)

    assert loader.call_args_list[0].args == (str(last_checkpoint),)
    train_kwargs = resumed_model.train.call_args.kwargs
    assert train_kwargs["resume"] is True
    assert train_kwargs["data"] == str(run_dir / "dataset")


def test_run_marks_failure_and_exits_when_training_crashes(tmp_path: Path) -> None:
    """Training exceptions should be surfaced through status.json and a non-zero exit."""
    run_dir = tmp_path / "run_failure"
    run_dir.mkdir()
    _write_params(run_dir)
    fake_model = MagicMock()
    fake_model.train.side_effect = RuntimeError("boom")

    with patch("fovux.core.train_worker.load_yolo_model", return_value=fake_model):
        with pytest.raises(SystemExit) as exc_info:
            run(run_dir)

    assert exc_info.value.code == 1
    status = json.loads((run_dir / "status.json").read_text())
    assert status["status"] == "failed"
    assert "RuntimeError" in status["error"]


@pytest.mark.filterwarnings(TRAIN_WORKER_RUNPY_WARNING)
def test_main_usage_error_exits_cleanly() -> None:
    """Executing the module without a run directory should log a usage error and exit."""
    fake_logger = MagicMock()
    with (
        patch("fovux.core.logging.get_logger", return_value=fake_logger),
        patch("fovux.core.logging.configure_logging") as configure_logging,
        patch.object(sys, "argv", ["train_worker"]),
    ):
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("fovux.core.train_worker", run_name="__main__")

    assert exc_info.value.code == 1
    configure_logging.assert_called_once_with()
    fake_logger.error.assert_called_once()


@pytest.mark.filterwarnings(TRAIN_WORKER_RUNPY_WARNING)
def test_main_runs_worker_when_path_is_provided(tmp_path: Path) -> None:
    """Executing the module with a run directory should invoke the worker path."""
    run_dir = tmp_path / "run_script"
    run_dir.mkdir()
    _write_params(run_dir)
    fake_logger = MagicMock()
    fake_model = MagicMock()

    with (
        patch("fovux.core.logging.get_logger", return_value=fake_logger),
        patch("fovux.core.logging.configure_logging"),
        patch("fovux.core.ultralytics_adapter.load_yolo_model", return_value=fake_model),
        patch.object(sys, "argv", ["train_worker", str(run_dir)]),
    ):
        runpy.run_module("fovux.core.train_worker", run_name="__main__")

    assert fake_model.train.called

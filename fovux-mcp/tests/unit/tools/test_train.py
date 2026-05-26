"""Tests for training tools: train_start, train_status, train_stop, train_resume."""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fovux.core.errors import (
    FovuxDatasetNotFoundError,
    FovuxTrainingAlreadyRunningError,
    FovuxTrainingRunNotFoundError,
    FovuxTrainingSubprocessError,
)
from fovux.core.paths import FovuxPaths
from fovux.core.processes import ProcessIdentity, TerminationResult, command_fingerprint
from fovux.core.runs import RunRegistry, get_registry
from fovux.schemas.training import (
    TrainResumeInput,
    TrainStartInput,
    TrainStatusInput,
    TrainStopInput,
)
from fovux.tools.train_resume import _run_train_resume
from fovux.tools.train_start import _run_train_start
from fovux.tools.train_status import _pid_alive, _read_metrics, _run_train_status
from fovux.tools.train_stop import _kill_pid, _run_train_stop

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


def _make_registry(tmp_path: Path) -> RunRegistry:
    return RunRegistry(tmp_path / "runs.db")


def _fake_popen(pid: int = 99999) -> MagicMock:
    mock = MagicMock()
    mock.pid = pid
    mock.poll.return_value = None
    return mock


def _registry_extra(paths: FovuxPaths, run_id: str) -> dict[str, object]:
    record = get_registry(paths.runs_db).get_run(run_id)
    assert record is not None
    raw = record.extra_json
    if raw is None:
        payload: object = {}
    elif isinstance(raw, dict):
        payload = raw
    elif isinstance(raw, str):
        payload = json.loads(raw)
    else:
        payload = json.loads(str(raw))
    assert isinstance(payload, dict)
    return payload


@pytest.fixture()
def fake_fovux_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def fake_train_start_process_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep train tool tests focused on registry behavior instead of live procfs."""

    def capture(*, pid: int, command: list[str], cwd: Path) -> ProcessIdentity:
        return ProcessIdentity(
            pid=pid,
            command_fingerprint=command_fingerprint(command),
            cwd=str(cwd.expanduser().resolve(strict=False)),
            start_marker="unit-test-start",
            process_group_id=None,
            platform="unit-test",
        )

    monkeypatch.setattr("fovux.tools.train_start.capture_process_identity", capture)
    monkeypatch.setattr("fovux.tools.train_resume.capture_process_identity", capture)


# ──────────────────────────────────────────────
# train_start
# ──────────────────────────────────────────────


def test_train_start_returns_run_id(fake_fovux_home, tmp_path):
    """train_start should return a run_id and status=running."""
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen()) as _mock:
        out = _run_train_start(
            TrainStartInput(
                dataset_path=FIXTURES / "mini_yolo",
                model="yolov8n.pt",
                epochs=1,
            )
        )
    assert out.run_id
    assert out.status == "running"
    assert out.pid == 99999


def test_train_start_missing_dataset_raises(fake_fovux_home):
    """Should raise FovuxDatasetNotFoundError for nonexistent dataset."""
    with pytest.raises(FovuxDatasetNotFoundError):
        _run_train_start(TrainStartInput(dataset_path=Path("/no/such/dataset")))


def test_train_start_writes_params_json(fake_fovux_home):
    """params.json should be written to the run directory."""
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen()):
        out = _run_train_start(
            TrainStartInput(
                dataset_path=FIXTURES / "mini_yolo",
                epochs=5,
            )
        )
    params = json.loads((out.run_path / "params.json").read_text())
    assert params["epochs"] == 5


def test_train_start_custom_name(fake_fovux_home):
    """Custom name should be used as run_id."""
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen()):
        out = _run_train_start(
            TrainStartInput(
                dataset_path=FIXTURES / "mini_yolo",
                name="my_custom_run",
            )
        )
    assert out.run_id == "my_custom_run"


def test_train_start_rejects_existing_complete_run_without_force(fake_fovux_home):
    """Existing completed runs should not be overwritten unless force=True."""
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen()):
        out = _run_train_start(
            TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="repeatable")
        )
    assert out.run_path == FovuxPaths(fake_fovux_home).runs / "repeatable"

    registry = get_registry(FovuxPaths(fake_fovux_home).runs_db)
    registry.update_status(out.run_id, "complete")
    assert registry.get_run(out.run_id).status == "complete"  # type: ignore[union-attr]

    with (
        patch("fovux.tools.train_start.get_registry", return_value=registry),
        pytest.raises(FovuxTrainingAlreadyRunningError, match="already exists"),
    ):
        retry_input = TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="repeatable")
        assert retry_input.force is False
        _run_train_start(retry_input)


def test_train_start_force_overwrites_finished_run(fake_fovux_home):
    """force=True should allow a stopped/failed/complete run name to be reused."""
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=100)):
        out = _run_train_start(
            TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="retryable")
        )
    (out.run_path / "metrics.jsonl").write_text('{"epoch": 1}\n', encoding="utf-8")

    registry = get_registry(FovuxPaths(fake_fovux_home).runs_db)
    registry.update_status(out.run_id, "failed")

    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=101)):
        forced = _run_train_start(
            TrainStartInput(
                dataset_path=FIXTURES / "mini_yolo",
                name="retryable",
                force=True,
            )
        )

    assert forced.run_id == "retryable"
    assert forced.pid == 101
    assert not (forced.run_path / "metrics.jsonl").exists()


def test_train_start_enforces_max_concurrent_runs(fake_fovux_home):
    """max_concurrent_runs should prevent accidentally saturating the host."""
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=100)):
        _run_train_start(
            TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="already_running")
        )

    with pytest.raises(FovuxTrainingAlreadyRunningError, match="concurrent"):
        _run_train_start(
            TrainStartInput(
                dataset_path=FIXTURES / "mini_yolo",
                name="second_run",
                max_concurrent_runs=1,
            )
        )


def test_train_start_marks_failed_when_subprocess_spawn_fails(fake_fovux_home):
    """Subprocess spawn failures should leave a failed registry row instead of a ghost run."""
    with patch(
        "fovux.tools.train_start.subprocess.Popen",
        side_effect=OSError("python missing"),
    ):
        with pytest.raises(FovuxTrainingSubprocessError, match="python missing"):
            _run_train_start(
                TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="spawn_failure")
            )

    registry = get_registry(FovuxPaths(fake_fovux_home).runs_db)
    record = registry.get_run("spawn_failure")
    assert record is not None
    assert record.status == "failed"


def test_train_start_writes_json_pid_file_atomically(fake_fovux_home):
    """pid.txt should contain a structured payload for robust future parsing."""
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=4567)):
        out = _run_train_start(TrainStartInput(dataset_path=FIXTURES / "mini_yolo"))

    payload = json.loads((out.run_path / "pid.txt").read_text(encoding="utf-8"))
    assert payload["pid"] == 4567
    assert payload["process"]["pid"] == 4567
    assert isinstance(payload["process"]["command_fingerprint"], str)


def test_train_start_terminates_worker_when_bookkeeping_fails(fake_fovux_home):
    """Post-spawn metadata failures should not leave a detached worker running."""
    proc = _fake_popen(pid=4568)
    with (
        patch("fovux.tools.train_start.subprocess.Popen", return_value=proc),
        patch(
            "fovux.tools.train_start.capture_process_identity",
            side_effect=RuntimeError("snapshot failed"),
        ),
        pytest.raises(FovuxTrainingSubprocessError, match="snapshot failed"),
    ):
        _run_train_start(TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="bad_meta"))

    proc.terminate.assert_called_once()
    record = get_registry(FovuxPaths(fake_fovux_home).runs_db).get_run("bad_meta")
    assert record is not None
    assert record.status == "failed"


def test_train_start_terminates_worker_group_after_identity_capture(fake_fovux_home):
    """Post-identity bookkeeping failures should clean up the isolated worker group."""
    proc = _fake_popen(pid=4569)

    def fail_pid_write(path: Path, payload: object) -> None:
        if path.name == "pid.txt":
            raise RuntimeError("pid write failed")

    with (
        patch("fovux.tools.train_start.subprocess.Popen", return_value=proc),
        patch("fovux.tools.train_start.write_json_atomically", side_effect=fail_pid_write),
        patch("fovux.tools.train_start.terminate_process_tree") as terminate,
        pytest.raises(FovuxTrainingSubprocessError, match="pid write failed"),
    ):
        terminate.return_value = TerminationResult(
            status="terminated",
            signal_sent=True,
            message="stopped",
        )
        _run_train_start(TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="bad_pid_write"))

    terminate.assert_called_once()
    identity = terminate.call_args.args[0]
    assert isinstance(identity, ProcessIdentity)
    assert identity.pid == 4569
    assert terminate.call_args.kwargs == {"force": True}
    proc.terminate.assert_not_called()
    record = get_registry(FovuxPaths(fake_fovux_home).runs_db).get_run("bad_pid_write")
    assert record is not None
    assert record.status == "failed"


def test_train_start_reports_worker_group_cleanup_failure(fake_fovux_home):
    """Failed post-identity cleanup should be visible and fall back to leader termination."""
    proc = _fake_popen(pid=4570)

    def fail_pid_write(path: Path, payload: object) -> None:
        if path.name == "pid.txt":
            raise RuntimeError("pid write failed")

    with (
        patch("fovux.tools.train_start.subprocess.Popen", return_value=proc),
        patch("fovux.tools.train_start.write_json_atomically", side_effect=fail_pid_write),
        patch("fovux.tools.train_start.terminate_process_tree") as terminate,
        pytest.raises(FovuxTrainingSubprocessError, match="cleanup failed: still alive"),
    ):
        terminate.return_value = TerminationResult(
            status="failed",
            signal_sent=True,
            message="still alive",
        )
        _run_train_start(TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="bad_cleanup"))

    terminate.assert_called_once()
    proc.terminate.assert_called_once()
    record = get_registry(FovuxPaths(fake_fovux_home).runs_db).get_run("bad_cleanup")
    assert record is not None
    assert record.status == "failed"


def test_train_start_reports_worker_group_cleanup_exception(fake_fovux_home):
    """Cleanup exceptions should not disappear behind the original bookkeeping failure."""
    proc = _fake_popen(pid=4571)

    def fail_pid_write(path: Path, payload: object) -> None:
        if path.name == "pid.txt":
            raise RuntimeError("pid write failed")

    with (
        patch("fovux.tools.train_start.subprocess.Popen", return_value=proc),
        patch("fovux.tools.train_start.write_json_atomically", side_effect=fail_pid_write),
        patch(
            "fovux.tools.train_start.terminate_process_tree",
            side_effect=RuntimeError("cleanup boom"),
        ) as terminate,
        pytest.raises(FovuxTrainingSubprocessError, match="cleanup failed: cleanup boom"),
    ):
        _run_train_start(
            TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="cleanup_exception")
        )

    terminate.assert_called_once()
    proc.terminate.assert_called_once()
    record = get_registry(FovuxPaths(fake_fovux_home).runs_db).get_run("cleanup_exception")
    assert record is not None
    assert record.status == "failed"


def test_train_start_defaults_to_auto_device() -> None:
    """TrainStartInput and train_start should default to automatic device selection."""
    from fovux.tools.train_start import train_start

    assert TrainStartInput(dataset_path=Path(".")).device == "auto"
    assert inspect.signature(train_start).parameters["device"].default == "auto"
    assert inspect.signature(train_start).parameters["force"].default is False
    assert inspect.signature(train_start).parameters["max_concurrent_runs"].default == 1


# ──────────────────────────────────────────────
# train_status
# ──────────────────────────────────────────────


def test_train_status_unknown_run_raises(fake_fovux_home):
    """Should raise FovuxTrainingRunNotFoundError for unknown run_id."""
    with pytest.raises(FovuxTrainingRunNotFoundError):
        _run_train_status(TrainStatusInput(run_id="does_not_exist"))


def test_train_status_reflects_registry(fake_fovux_home):
    """Status returned should match registry after launch."""
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=12345)):
        start_out = _run_train_start(
            TrainStartInput(
                dataset_path=FIXTURES / "mini_yolo",
            )
        )
    with patch("fovux.tools.train_status._pid_alive", return_value=True):
        status_out = _run_train_status(TrainStatusInput(run_id=start_out.run_id))
    assert status_out.status == "running"
    assert status_out.pid == 12345


def test_train_status_detects_complete_when_pid_gone(fake_fovux_home):
    """When pid is no longer alive and status.json says complete, status should be complete."""
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=1)):
        start_out = _run_train_start(
            TrainStartInput(
                dataset_path=FIXTURES / "mini_yolo",
            )
        )
    # write a status.json indicating completion
    (start_out.run_path / "status.json").write_text(json.dumps({"status": "complete"}))
    with patch("fovux.tools.train_status._pid_alive", return_value=False):
        status_out = _run_train_status(TrainStatusInput(run_id=start_out.run_id))
    assert status_out.status == "complete"


def test_read_metrics_from_results_csv(tmp_path):
    """_read_metrics should parse epoch and mAP50 from results.csv."""
    csv_content = "epoch,metrics/mAP50(B),metrics/mAP50-95(B)\n0,0.45,0.30\n1,0.52,0.35\n"
    csv_path = tmp_path / "results.csv"
    csv_path.write_text(csv_content)
    epoch, map50 = _read_metrics(tmp_path)
    assert epoch == 2
    assert abs(map50 - 0.52) < 1e-6


# ──────────────────────────────────────────────
# train_stop
# ──────────────────────────────────────────────


def test_train_stop_unknown_run_raises(fake_fovux_home):
    """Should raise FovuxTrainingRunNotFoundError for unknown run_id."""
    with pytest.raises(FovuxTrainingRunNotFoundError):
        _run_train_stop(TrainStopInput(run_id="ghost_run"))


def test_train_stop_uses_cached_registry(fake_fovux_home):
    """train_stop should use the shared process-local registry singleton."""
    with (
        patch("fovux.tools.train_stop.get_registry") as get_registry,
        patch(
            "fovux.tools.train_stop.RunRegistry",
            side_effect=AssertionError("direct registry"),
            create=True,
        ),
    ):
        get_registry.return_value.get_run.return_value = None
        with pytest.raises(FovuxTrainingRunNotFoundError):
            _run_train_stop(TrainStopInput(run_id="ghost_run"))

    get_registry.assert_called_once()


def test_train_stop_updates_status(fake_fovux_home):
    """train_stop should update registry status to stopped."""
    paths = FovuxPaths(fake_fovux_home)
    with patch(
        "fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=os.getpid())
    ):
        start_out = _run_train_start(
            TrainStartInput(
                dataset_path=FIXTURES / "mini_yolo",
            )
        )
    with patch(
        "fovux.tools.train_stop.terminate_process_tree",
        return_value=TerminationResult(
            status="terminated",
            signal_sent=True,
            message="Signal sent.",
        ),
    ):
        stop_out = _run_train_stop(TrainStopInput(run_id=start_out.run_id))
    assert stop_out.status == "stopped"
    extra = _registry_extra(paths, start_out.run_id)
    assert extra["process_stop_status"] == "terminated"
    assert extra["process_signal_sent"] is True
    assert extra["process_stale"] is False
    assert extra["stop_failure_class"] is None


def test_train_stop_noop_when_not_running(fake_fovux_home):
    """Stopping a non-running run should return its current status."""
    paths = FovuxPaths(fake_fovux_home)
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen()):
        start_out = _run_train_start(
            TrainStartInput(
                dataset_path=FIXTURES / "mini_yolo",
            )
        )
    with patch(
        "fovux.tools.train_stop.terminate_process_tree",
        return_value=TerminationResult(status="terminated", signal_sent=True, message="done"),
    ) as terminate:
        _run_train_stop(TrainStopInput(run_id=start_out.run_id))
        stop2 = _run_train_stop(TrainStopInput(run_id=start_out.run_id))
    terminate.assert_called_once()
    assert stop2.status == "stopped"
    assert "not running" in stop2.message.lower()
    extra = _registry_extra(paths, start_out.run_id)
    assert extra["process_stop_status"] == "terminated"
    assert extra["process_signal_sent"] is True
    assert extra["process_stale"] is False
    assert extra["stop_failure_class"] is None


def test_train_stop_refuses_pid_only_identity(fake_fovux_home):
    """A PID without recorded start/cmd/cwd metadata must not be signalled."""
    paths = FovuxPaths(fake_fovux_home)
    registry = get_registry(paths.runs_db)
    run_dir = paths.runs / "legacy_pid"
    run_dir.mkdir(parents=True)
    (run_dir / "pid.txt").write_text(json.dumps({"pid": 12345}), encoding="utf-8")
    registry.create_run(
        run_id="legacy_pid",
        run_path=run_dir,
        model="yolov8n.pt",
        dataset_path=FIXTURES / "mini_yolo",
        task="detect",
        epochs=1,
    )
    registry.update_status("legacy_pid", "running", pid=12345)

    with patch("fovux.tools.train_stop.terminate_process_tree") as terminate:
        out = _run_train_stop(TrainStopInput(run_id="legacy_pid"))

    terminate.assert_not_called()
    assert out.status == "running"
    assert "refusing" in out.message.lower()
    extra = _registry_extra(paths, "legacy_pid")
    assert extra["process_stop_status"] == "refused"
    assert extra["process_signal_sent"] is False
    assert extra["process_stale"] is True
    assert extra["stop_failure_class"] == "missing_process_identity"


def test_train_stop_refuses_escaped_run_path(fake_fovux_home, tmp_path):
    """Registry paths outside the runs root must not be used for process identity reads."""
    paths = FovuxPaths(fake_fovux_home)
    registry = get_registry(paths.runs_db)
    escaped_dir = tmp_path / "escaped"
    escaped_dir.mkdir()
    (escaped_dir / "pid.txt").write_text(
        json.dumps(
            {
                "pid": 12345,
                "process": {
                    "pid": 12345,
                    "command_fingerprint": command_fingerprint(["python", "-m", "fovux.cli"]),
                    "cwd": str(escaped_dir),
                    "start_marker": "unit-test-start",
                    "process_group_id": None,
                    "platform": "unit-test",
                },
            }
        ),
        encoding="utf-8",
    )
    registry.create_run(
        run_id="escaped_path",
        run_path=escaped_dir,
        model="yolov8n.pt",
        dataset_path=FIXTURES / "mini_yolo",
        task="detect",
        epochs=1,
    )
    registry.update_status("escaped_path", "running", pid=12345)

    with patch("fovux.tools.train_stop.terminate_process_tree") as terminate:
        out = _run_train_stop(TrainStopInput(run_id="escaped_path"))

    terminate.assert_not_called()
    assert out.status == "running"
    assert "refusing" in out.message.lower()
    extra = _registry_extra(paths, "escaped_path")
    assert extra["process_stop_status"] == "refused"
    assert extra["process_signal_sent"] is False
    assert extra["process_stale"] is True
    assert extra["stop_failure_class"] == "missing_process_identity"


def test_train_stop_refuses_mismatched_process_identity(fake_fovux_home):
    """A reused PID with mismatched process identity must stay untouched."""
    paths = FovuxPaths(fake_fovux_home)
    with patch(
        "fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=os.getpid())
    ):
        start_out = _run_train_start(TrainStartInput(dataset_path=FIXTURES / "mini_yolo"))

    with patch(
        "fovux.tools.train_stop.terminate_process_tree",
        return_value=TerminationResult(
            status="mismatch",
            signal_sent=False,
            message="PID no longer matches.",
        ),
    ):
        out = _run_train_stop(TrainStopInput(run_id=start_out.run_id))

    assert out.status == "running"
    assert "matches" in out.message
    extra = _registry_extra(paths, start_out.run_id)
    assert extra["process_stop_status"] == "mismatch"
    assert extra["process_signal_sent"] is False
    assert extra["process_stale"] is True
    assert extra["stop_failure_class"] == "process_identity_mismatch"


@pytest.mark.parametrize("result_status", ["permission_denied", "failed"])
def test_train_stop_keeps_run_running_when_signal_fails(fake_fovux_home, result_status: str):
    """Failed signal attempts must not mark a still-unknown process as stopped."""
    paths = FovuxPaths(fake_fovux_home)
    with patch(
        "fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=os.getpid())
    ):
        start_out = _run_train_start(TrainStartInput(dataset_path=FIXTURES / "mini_yolo"))

    with patch(
        "fovux.tools.train_stop.terminate_process_tree",
        return_value=TerminationResult(
            status=result_status,
            signal_sent=False,
            message=f"signal {result_status}",
        ),
    ):
        out = _run_train_stop(TrainStopInput(run_id=start_out.run_id))

    record = get_registry(paths.runs_db).get_run(start_out.run_id)
    assert record is not None
    assert out.status == "running"
    assert record.status == "running"
    extra = _registry_extra(paths, start_out.run_id)
    assert extra["process_stop_status"] == result_status
    assert extra["process_signal_sent"] is False
    assert extra["process_stale"] is True
    assert extra["stop_failure_class"] == f"process_signal_{result_status}"


def test_train_stop_marks_missing_process_stopped_with_stale_audit(fake_fovux_home):
    """A recorded process that has already exited can be closed with stale audit context."""
    paths = FovuxPaths(fake_fovux_home)
    with patch(
        "fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=os.getpid())
    ):
        start_out = _run_train_start(TrainStartInput(dataset_path=FIXTURES / "mini_yolo"))

    with patch(
        "fovux.tools.train_stop.terminate_process_tree",
        return_value=TerminationResult(
            status="missing",
            signal_sent=False,
            message="PID no longer exists.",
        ),
    ):
        out = _run_train_stop(TrainStopInput(run_id=start_out.run_id))

    record = get_registry(paths.runs_db).get_run(start_out.run_id)
    assert record is not None
    assert out.status == "stopped"
    assert record.status == "stopped"
    extra = _registry_extra(paths, start_out.run_id)
    assert extra["process_stop_status"] == "missing"
    assert extra["process_signal_sent"] is False
    assert extra["process_stale"] is True
    assert extra["stop_failure_class"] == "missing_process"


def test_train_resume_unknown_run_raises(fake_fovux_home):
    """Resuming an unknown run should raise the training not found error."""
    with pytest.raises(FovuxTrainingRunNotFoundError):
        _run_train_resume(TrainResumeInput(run_id="ghost_run"))


def test_train_resume_updates_params_and_status(fake_fovux_home):
    """Resuming should persist the checkpoint path, new epoch count, and running status."""
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=11111)):
        start_out = _run_train_start(TrainStartInput(dataset_path=FIXTURES / "mini_yolo"))

    last_pt = start_out.run_path / "weights" / "last.pt"
    last_pt.parent.mkdir(parents=True, exist_ok=True)
    last_pt.write_bytes(b"weights")

    with (
        patch("fovux.tools.train_resume.sys.platform", "linux"),
        patch(
            "fovux.tools.train_resume.subprocess.Popen", return_value=_fake_popen(pid=22222)
        ) as popen,
    ):
        resume_out = _run_train_resume(TrainResumeInput(run_id=start_out.run_id, epochs=9))

    params = json.loads((start_out.run_path / "params.json").read_text())
    pid_payload = json.loads((start_out.run_path / "pid.txt").read_text(encoding="utf-8"))
    assert resume_out.status == "running"
    assert resume_out.pid == 22222
    assert popen.call_args.kwargs["start_new_session"] is True
    assert pid_payload["pid"] == 22222
    assert pid_payload["process"]["pid"] == 22222
    assert params["resume_checkpoint"] == str(last_pt)
    assert params["epochs"] == 9


def test_train_resume_uses_windows_process_group(fake_fovux_home):
    """Windows resumed workers should be isolated in their own process group."""
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=11111)):
        start_out = _run_train_start(TrainStartInput(dataset_path=FIXTURES / "mini_yolo"))

    with (
        patch("fovux.tools.train_resume.sys.platform", "win32"),
        patch(
            "fovux.tools.train_resume.subprocess.CREATE_NEW_PROCESS_GROUP",
            512,
            create=True,
        ),
        patch(
            "fovux.tools.train_resume.subprocess.Popen", return_value=_fake_popen(pid=44444)
        ) as popen,
    ):
        _run_train_resume(TrainResumeInput(run_id=start_out.run_id))

    assert popen.call_args.kwargs["creationflags"] == 512


def test_train_resume_marks_failed_when_spawn_fails(fake_fovux_home):
    """Resume spawn failures should leave a failed registry row."""
    paths = FovuxPaths(fake_fovux_home)
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=11111)):
        start_out = _run_train_start(
            TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="resume_spawn_failure")
        )

    with (
        patch("fovux.tools.train_resume.subprocess.Popen", side_effect=OSError("python missing")),
        pytest.raises(FovuxTrainingSubprocessError, match="python missing"),
    ):
        _run_train_resume(TrainResumeInput(run_id=start_out.run_id))

    record = get_registry(paths.runs_db).get_run(start_out.run_id)
    assert record is not None
    assert record.status == "failed"


def test_train_resume_terminates_worker_when_bookkeeping_fails(fake_fovux_home):
    """Resume metadata failures should not leave a detached worker running."""
    paths = FovuxPaths(fake_fovux_home)
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=11111)):
        start_out = _run_train_start(
            TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="resume_bad_meta")
        )

    proc = _fake_popen(pid=55555)
    with (
        patch("fovux.tools.train_resume.subprocess.Popen", return_value=proc),
        patch(
            "fovux.tools.train_resume.capture_process_identity",
            side_effect=RuntimeError("snapshot failed"),
        ),
        pytest.raises(FovuxTrainingSubprocessError, match="snapshot failed"),
    ):
        _run_train_resume(TrainResumeInput(run_id=start_out.run_id))

    proc.terminate.assert_called_once()
    record = get_registry(paths.runs_db).get_run(start_out.run_id)
    assert record is not None
    assert record.status == "failed"


def test_train_resume_terminates_worker_group_after_identity_capture(fake_fovux_home):
    """Resume post-identity failures should clean up the isolated worker group."""
    paths = FovuxPaths(fake_fovux_home)
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=11111)):
        start_out = _run_train_start(
            TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="resume_bad_pid_write")
        )

    proc = _fake_popen(pid=55556)

    def fail_pid_write(path: Path, payload: object) -> None:
        if path.name == "pid.txt":
            raise RuntimeError("pid write failed")

    with (
        patch("fovux.tools.train_resume.subprocess.Popen", return_value=proc),
        patch("fovux.tools.train_resume.write_json_atomically", side_effect=fail_pid_write),
        patch("fovux.tools.train_resume.terminate_process_tree") as terminate,
        pytest.raises(FovuxTrainingSubprocessError, match="pid write failed"),
    ):
        terminate.return_value = TerminationResult(
            status="terminated",
            signal_sent=True,
            message="stopped",
        )
        _run_train_resume(TrainResumeInput(run_id=start_out.run_id))

    terminate.assert_called_once()
    identity = terminate.call_args.args[0]
    assert isinstance(identity, ProcessIdentity)
    assert identity.pid == 55556
    assert terminate.call_args.kwargs == {"force": True}
    proc.terminate.assert_not_called()
    record = get_registry(paths.runs_db).get_run(start_out.run_id)
    assert record is not None
    assert record.status == "failed"


def test_train_resume_reports_worker_group_cleanup_failure(fake_fovux_home):
    """Resume cleanup failures should be visible and fall back to leader termination."""
    paths = FovuxPaths(fake_fovux_home)
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=11111)):
        start_out = _run_train_start(
            TrainStartInput(dataset_path=FIXTURES / "mini_yolo", name="resume_bad_cleanup")
        )

    proc = _fake_popen(pid=55557)

    def fail_pid_write(path: Path, payload: object) -> None:
        if path.name == "pid.txt":
            raise RuntimeError("pid write failed")

    with (
        patch("fovux.tools.train_resume.subprocess.Popen", return_value=proc),
        patch("fovux.tools.train_resume.write_json_atomically", side_effect=fail_pid_write),
        patch("fovux.tools.train_resume.terminate_process_tree") as terminate,
        pytest.raises(FovuxTrainingSubprocessError, match="cleanup failed: still alive"),
    ):
        terminate.return_value = TerminationResult(
            status="failed",
            signal_sent=True,
            message="still alive",
        )
        _run_train_resume(TrainResumeInput(run_id=start_out.run_id))

    terminate.assert_called_once()
    proc.terminate.assert_called_once()
    record = get_registry(paths.runs_db).get_run(start_out.run_id)
    assert record is not None
    assert record.status == "failed"


def test_train_resume_falls_back_when_last_checkpoint_is_missing(fake_fovux_home):
    """Runs without a last checkpoint should still resume with a null checkpoint field."""
    with patch("fovux.tools.train_start.subprocess.Popen", return_value=_fake_popen(pid=11111)):
        start_out = _run_train_start(TrainStartInput(dataset_path=FIXTURES / "mini_yolo"))

    with patch("fovux.tools.train_resume.subprocess.Popen", return_value=_fake_popen(pid=33333)):
        _run_train_resume(TrainResumeInput(run_id=start_out.run_id))

    params = json.loads((start_out.run_path / "params.json").read_text())
    assert params["resume_checkpoint"] is None


# ──────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────


def test_pid_alive_current_process():
    """Current process PID should be alive."""
    assert _pid_alive(os.getpid()) is True


def test_pid_alive_bogus_pid():
    """A very large bogus PID should not be alive."""
    assert _pid_alive(2_000_000) is False


def test_kill_pid_uses_sigterm(monkeypatch):
    """POSIX stop requests should send SIGTERM when force is disabled."""
    import signal

    from fovux.tools import train_stop as train_stop_module

    monkeypatch.setattr(train_stop_module.sys, "platform", "linux")
    with patch.object(train_stop_module.os, "kill") as kill:
        message = _kill_pid(321, force=False)

    kill.assert_called_once_with(321, signal.SIGTERM)
    assert "Signal sent" in message


def test_kill_pid_uses_taskkill_on_windows(monkeypatch):
    """Windows stop requests should delegate to taskkill and honor force mode."""
    from fovux.tools import train_stop as train_stop_module

    monkeypatch.setattr(train_stop_module.sys, "platform", "win32")
    with patch.object(train_stop_module.subprocess, "run") as run:
        message = _kill_pid(654, force=True)

    run.assert_called_once_with(["taskkill", "/PID", "654", "/F"], capture_output=True, check=False)
    assert "Signal sent" in message


def test_kill_pid_handles_missing_process(monkeypatch):
    """A missing process should return a descriptive noop message."""
    from fovux.tools import train_stop as train_stop_module

    monkeypatch.setattr(train_stop_module.sys, "platform", "linux")
    with patch.object(train_stop_module.os, "kill", side_effect=ProcessLookupError):
        message = _kill_pid(999, force=True)

    assert "no longer exists" in message

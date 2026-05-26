"""Tests for structured logging and tool lifecycle events."""

from __future__ import annotations

import json

import pytest

from fovux.core.errors import FovuxCheckpointNotFoundError, FovuxError
from fovux.core.logging import configure_logging, get_logger
from fovux.core.tooling import tool_event


def test_configure_logging_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON format should emit structured JSON lines to stderr."""
    configure_logging(level="INFO", fmt="json")
    get_logger(__name__).info("json_log_test", answer=42)

    captured = capsys.readouterr().err.strip()
    payload = json.loads(captured)
    assert payload["event"] == "json_log_test"
    assert payload["answer"] == 42
    assert payload["level"] == "info"


def test_configure_logging_pretty_honors_no_color(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pretty format should avoid ANSI color codes when NO_COLOR is set."""
    monkeypatch.setenv("NO_COLOR", "1")
    configure_logging(level="INFO", fmt="pretty")
    get_logger(__name__).info("pretty_log_test", flag=True)

    captured = capsys.readouterr().err
    assert "pretty_log_test" in captured
    assert "\u001b[" not in captured


def test_configure_logging_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    """Repeated configure_logging calls should reconfigure cleanly."""
    configure_logging(level="WARNING", fmt="json")
    configure_logging(level="INFO", fmt="json")
    get_logger(__name__).info("idempotent_log_test")

    payload = json.loads(capsys.readouterr().err.strip())
    assert payload["event"] == "idempotent_log_test"
    assert payload["level"] == "info"


def test_tool_event_binds_run_id(capsys: pytest.CaptureFixture[str]) -> None:
    """tool_event should emit start/end logs with bound run_id context."""
    configure_logging(level="INFO", fmt="json")

    with tool_event("dataset_inspect", run_id="run_test", dataset_path="dataset_root"):
        pass

    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line.strip()]
    assert lines[0]["event"] == "tool_start"
    assert lines[0]["run_id"] == "run_test"
    assert lines[0]["tool_name"] == "dataset_inspect"
    assert lines[-1]["event"] == "tool_end"


def test_tool_event_logs_fovux_errors(capsys: pytest.CaptureFixture[str]) -> None:
    """tool_event should surface FovuxError metadata in error logs."""
    from fovux.core.errors import FovuxDatasetNotFoundError

    configure_logging(level="INFO", fmt="json")

    with pytest.raises(FovuxDatasetNotFoundError):
        with tool_event("dataset_inspect", run_id="run_err"):
            raise FovuxDatasetNotFoundError("/missing")

    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line.strip()]
    assert lines[-1]["event"] == "tool_error"
    assert lines[-1]["error_code"] == "FOVUX_DATASET_001"
    assert lines[-1]["run_id"] == "run_err"


def test_tool_event_wraps_missing_files() -> None:
    """Tool boundaries should convert raw FileNotFoundError into typed Fovux errors."""
    with pytest.raises(FovuxCheckpointNotFoundError):
        with tool_event("export_onnx"):
            raise FileNotFoundError("missing.pt")


def test_tool_event_wraps_underlying_runtime_errors() -> None:
    """Tool boundaries should hide raw library RuntimeError/AssertionError details."""
    with pytest.raises(FovuxError, match="Underlying library error in eval_run"):
        with tool_event("eval_run"):
            raise RuntimeError("ultralytics exploded")

"""Unit tests for registry lifecycle policies."""

from __future__ import annotations

from datetime import datetime

import pytest

from fovux.core.run_registry.lifecycle import (
    OperationLifecyclePolicy,
    RunLifecyclePolicy,
)
from fovux.core.run_registry.models import OperationRecord, RunRecord

NOW = datetime(2026, 7, 23, 12, 0, 0)


def _run(status: str = "pending") -> RunRecord:
    return RunRecord(
        id="run_policy",
        status=status,
        model="yolo.pt",
        dataset_path="dataset",
        task="detect",
        epochs=1,
        run_path="runs/run_policy",
        tags_json="[]",
        extra_json="{}",
    )


def _operation(status: str = "pending") -> OperationRecord:
    return OperationRecord(
        id="op_policy",
        tool="model_list",
        arguments_json="{}",
        status=status,
    )


def test_run_policy_applies_timestamps_and_pid() -> None:
    record = _run()

    changed = RunLifecyclePolicy.apply(record, "running", pid=42, now=NOW)

    assert changed is True
    assert record.status == "running"
    assert record.pid == 42
    assert record.started_at == NOW
    assert record.finished_at is None


def test_run_policy_rejects_invalid_transition_without_mutation() -> None:
    record = _run("complete")

    with pytest.raises(ValueError, match="Invalid run status transition"):
        RunLifecyclePolicy.apply(record, "pending", pid=None, now=NOW)

    assert record.status == "complete"
    assert record.finished_at is None


def test_operation_policy_rejects_terminal_rewrite() -> None:
    record = _operation("succeeded")

    with pytest.raises(ValueError, match="Invalid operation status transition"):
        OperationLifecyclePolicy.apply(record, "failed", now=NOW)

    assert record.status == "succeeded"


def test_same_state_is_not_a_transition() -> None:
    record = _operation("running")

    changed = OperationLifecyclePolicy.apply(record, "running", now=NOW)

    assert changed is False
    assert record.started_at == NOW

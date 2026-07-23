"""Central lifecycle policy for run and background-operation records."""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

from fovux.core.run_registry.models import OperationRecord, RunRecord

RunStatus = Literal["pending", "running", "complete", "failed", "stopped", "archived"]
OperationStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]

RUN_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset(
    {"complete", "failed", "stopped", "archived"}
)
OPERATION_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset({"succeeded", "failed", "cancelled"})

RUN_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "pending": frozenset({"running", "complete", "failed", "stopped", "archived"}),
    "running": frozenset({"complete", "failed", "stopped", "archived"}),
    "complete": frozenset({"running", "archived"}),
    "failed": frozenset({"running", "archived"}),
    "stopped": frozenset({"running", "archived"}),
    "archived": frozenset({"pending", "running"}),
}

OPERATION_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "pending": frozenset({"running", "failed", "cancelled"}),
    "running": frozenset({"succeeded", "failed", "cancelled"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


class RunLifecyclePolicy:
    """Validate and apply run status transitions and timestamps."""

    @staticmethod
    def apply(
        record: RunRecord,
        target: RunStatus,
        *,
        pid: int | None,
        now: datetime,
    ) -> bool:
        """Apply one transition and return whether the status value changed."""
        current = str(record.status)
        changed = current != target
        if changed and target not in RUN_TRANSITIONS.get(current, frozenset()):
            raise ValueError(f"Invalid run status transition from '{current}' to '{target}'")

        record.status = target  # type: ignore[assignment]
        if pid is not None:
            record.pid = pid  # type: ignore[assignment]
        if target == "running" and record.started_at is None:
            record.started_at = now
        if target in RUN_TERMINAL_STATUSES:
            record.finished_at = now  # type: ignore[assignment]
        return changed


class OperationLifecyclePolicy:
    """Validate and apply operation status transitions and timestamps."""

    @staticmethod
    def apply(
        record: OperationRecord,
        target: OperationStatus,
        *,
        now: datetime,
    ) -> bool:
        """Apply one transition and return whether the status value changed."""
        current = str(record.status)
        changed = current != target
        if changed and target not in OPERATION_TRANSITIONS.get(current, frozenset()):
            raise ValueError(f"Invalid operation status transition from '{current}' to '{target}'")

        record.status = target  # type: ignore[assignment]
        if target == "running" and record.started_at is None:
            record.started_at = now
        if target in OPERATION_TERMINAL_STATUSES:
            record.finished_at = now  # type: ignore[assignment]
        return changed


__all__ = [
    "OPERATION_TERMINAL_STATUSES",
    "OPERATION_TRANSITIONS",
    "OperationLifecyclePolicy",
    "OperationStatus",
    "RUN_TERMINAL_STATUSES",
    "RUN_TRANSITIONS",
    "RunLifecyclePolicy",
    "RunStatus",
]

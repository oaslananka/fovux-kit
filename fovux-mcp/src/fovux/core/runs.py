"""Stable compatibility facade for the SQLite-backed run registry."""

from __future__ import annotations

import threading
from pathlib import Path

from fovux.core.run_registry.facade import RunRegistry
from fovux.core.run_registry.lifecycle import OperationStatus, RunStatus
from fovux.core.run_registry.models import (
    ArtifactRecord,
    AuditEventRecord,
    Base,
    DatasetRecord,
    ExportRecord,
    MetricRecord,
    ModelRecord,
    OperationEventRecord,
    OperationRecord,
    ReviewQueueEntry,
    RunEventRecord,
    RunRecord,
    SchemaMigrationRecord,
    TagRecord,
    UtcDateTime,
    _deserialize_datetime,
    _serialize_datetime,
    _utcnow_naive,
)

_REGISTRIES: dict[Path, RunRegistry] = {}
_REGISTRIES_LOCK = threading.Lock()


def get_registry(db_path: Path) -> RunRegistry:
    """Return a process-local singleton registry for a database path."""
    resolved = db_path.expanduser().resolve()
    with _REGISTRIES_LOCK:
        registry = _REGISTRIES.get(resolved)
        if registry is None:
            registry = RunRegistry(resolved)
            _REGISTRIES[resolved] = registry
        return registry


def close_registry(db_path: Path | None = None) -> None:
    """Dispose cached registry engines for one database or all databases."""
    if db_path is None:
        with _REGISTRIES_LOCK:
            registries = list(_REGISTRIES.values())
            _REGISTRIES.clear()
        for registry in registries:
            registry.close()
        return

    resolved = db_path.expanduser().resolve()
    with _REGISTRIES_LOCK:
        cached_registry = _REGISTRIES.pop(resolved) if resolved in _REGISTRIES else None
    if cached_registry is not None:
        cached_registry.close()


__all__ = [
    "ArtifactRecord",
    "AuditEventRecord",
    "Base",
    "DatasetRecord",
    "ExportRecord",
    "MetricRecord",
    "ModelRecord",
    "OperationEventRecord",
    "OperationRecord",
    "OperationStatus",
    "ReviewQueueEntry",
    "RunEventRecord",
    "RunRecord",
    "RunRegistry",
    "RunStatus",
    "SchemaMigrationRecord",
    "TagRecord",
    "UtcDateTime",
    "_deserialize_datetime",
    "_serialize_datetime",
    "_utcnow_naive",
    "close_registry",
    "get_registry",
]

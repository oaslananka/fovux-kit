"""Compatibility facade composed from focused registry repositories."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from fovux.core.run_registry.artifact_repository import ArtifactRepository
from fovux.core.run_registry.catalog_repository import CatalogRepository
from fovux.core.run_registry.database import RegistryDatabase
from fovux.core.run_registry.events import EventStore
from fovux.core.run_registry.lifecycle import RunStatus
from fovux.core.run_registry.metadata import RunMetadataProvider
from fovux.core.run_registry.models import (
    ArtifactRecord,
    AuditEventRecord,
    DatasetRecord,
    ExportRecord,
    MetricRecord,
    OperationEventRecord,
    OperationRecord,
    ReviewQueueEntry,
    RunEventRecord,
    RunRecord,
)
from fovux.core.run_registry.operation_repository import OperationRepository
from fovux.core.run_registry.run_repository import RunCreateRequest, RunRepository


class RunRegistry:
    """CRUD compatibility facade for the SQLite runs registry.

    Args:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: Path) -> None:
        """Compose focused repositories over one SQLite database boundary."""
        self._database = RegistryDatabase(db_path)
        self._engine: Engine = self._database.engine
        self._Session: sessionmaker[Session] = self._database.session_factory
        self._metadata = RunMetadataProvider()
        self._events = EventStore(self._Session)
        self._catalog = CatalogRepository(self._Session, self._metadata)
        self._runs = RunRepository(
            self._Session,
            metadata_provider=self._metadata,
            event_store=self._events,
            catalog_repository=self._catalog,
        )
        self._operations = OperationRepository(self._Session)
        self._artifacts = ArtifactRepository(
            self._Session,
            metadata_provider=self._metadata,
            event_store=self._events,
        )

    def close(self) -> None:
        """Dispose the SQLite engine and release pooled connections."""
        self._database.close()

    # Compatibility boundary: callers rely on the complete historical signature.
    def reserve_run_slot(
        self,  # NOSONAR(S107)
        run_id: str,
        run_path: Path,
        model: str,
        dataset_path: Path,
        task: str,
        epochs: int,
        max_concurrent_runs: int,
        tags: list[str] | None = None,
        extra: dict[str, Any] | None = None,
        dataset_fingerprint: str | None = None,
        config_hash: str | None = None,
        code_version: str | None = None,
        env_summary: str | None = None,
        parent_run_id: str | None = None,
    ) -> RunRecord:
        """Reserve a run slot atomically."""
        request = RunCreateRequest(
            run_id=run_id,
            run_path=run_path,
            model=model,
            dataset_path=dataset_path,
            task=task,
            epochs=epochs,
            tags=tags,
            extra=extra,
            dataset_fingerprint=dataset_fingerprint,
            config_hash=config_hash,
            code_version=code_version,
            env_summary=env_summary,
            parent_run_id=parent_run_id,
        )
        return self._runs.reserve_run_slot(request, max_concurrent_runs)

    def create_run(
        self,
        run_id: str,
        run_path: Path,
        model: str,
        dataset_path: Path,
        task: str,
        epochs: int,
        tags: list[str] | None = None,
        extra: dict[str, Any] | None = None,
        dataset_fingerprint: str | None = None,
        config_hash: str | None = None,
        code_version: str | None = None,
        env_summary: str | None = None,
        parent_run_id: str | None = None,
    ) -> RunRecord:
        """Insert a new run record."""
        request = RunCreateRequest(
            run_id=run_id,
            run_path=run_path,
            model=model,
            dataset_path=dataset_path,
            task=task,
            epochs=epochs,
            tags=tags,
            extra=extra,
            dataset_fingerprint=dataset_fingerprint,
            config_hash=config_hash,
            code_version=code_version,
            env_summary=env_summary,
            parent_run_id=parent_run_id,
        )
        return self._runs.create_run(request)

    def get_run(self, run_id: str) -> RunRecord | None:
        """Fetch a run by ID."""
        return self._runs.get_run(run_id)

    def update_status(
        self,
        run_id: str,
        status: RunStatus,
        pid: int | None = None,
    ) -> None:
        """Update run status and optional process ID."""
        self._runs.update_status(run_id, status, pid)

    def list_runs(
        self,
        status: RunStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RunRecord]:
        """List runs, optionally filtered by status."""
        return self._runs.list_runs(status, limit, offset)

    def delete_run(self, run_id: str) -> bool:
        """Delete a run record."""
        return self._runs.delete_run(run_id)

    def update_tags(self, run_id: str, tags: list[str]) -> bool:
        """Replace a run's tag list."""
        return self._runs.update_tags(run_id, tags)

    def update_extra(self, run_id: str, extra: dict[str, Any]) -> bool:
        """Merge extra metadata into a run record."""
        return self._runs.update_extra(run_id, extra)

    def create_operation(
        self,
        op_id: str,
        tool: str,
        arguments: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> OperationRecord:
        """Insert a new operation record."""
        return self._operations.create_operation(
            op_id,
            tool,
            arguments,
            idempotency_key,
        )

    def get_operation(self, op_id: str) -> OperationRecord | None:
        """Fetch an operation by ID."""
        return self._operations.get_operation(op_id)

    def get_operation_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> OperationRecord | None:
        """Fetch an operation by idempotency key."""
        return self._operations.get_operation_by_idempotency_key(idempotency_key)

    def update_operation_status(
        self,
        op_id: str,
        status: str,
        error_type: str | None = None,
        error: str | None = None,
        result: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> None:
        """Update operation lifecycle fields."""
        self._operations.update_operation_status(
            op_id,
            status,
            error_type,
            error,
            result,
            run_id,
        )

    def update_operation_progress(self, op_id: str, progress: int) -> None:
        """Update operation progress percentage."""
        self._operations.update_operation_progress(op_id, progress)

    def list_operations(self, limit: int = 100) -> list[OperationRecord]:
        """List operations ordered by creation time descending."""
        return self._operations.list_operations(limit)

    def create_operation_event(
        self,
        op_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> OperationEventRecord:
        """Create a durable lifecycle event for an operation."""
        return self._events.create_operation_event(op_id, event_type, data)

    def list_operation_events(
        self,
        last_event_id: int | None = None,
        limit: int = 1000,
    ) -> list[OperationEventRecord]:
        """List operation events newer than an optional event ID."""
        return self._events.list_operation_events(last_event_id, limit)

    def add_artifact(
        self,
        artifact_id: str,
        run_id: str | None,
        artifact_type: str,
        path: Path,
        sha256: str | None = None,
        size: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ArtifactRecord:
        """Register or merge an artifact record."""
        return self._artifacts.add_artifact(
            artifact_id,
            run_id,
            artifact_type,
            path,
            sha256,
            size,
            extra,
        )

    def record_export(
        self,
        export_id: str,
        run_id: str | None,
        source_checkpoint: Path,
        artifact_path: Path,
        format: str,
        duration_s: float | None = None,
        validation_result: dict[str, Any] | None = None,
    ) -> ExportRecord:
        """Record a model export and its associated artifact."""
        return self._artifacts.record_export(
            export_id,
            run_id,
            source_checkpoint,
            artifact_path,
            format,
            duration_s,
            validation_result,
        )

    def list_run_events(
        self,
        run_id: str | None = None,
        limit: int = 1000,
    ) -> list[RunEventRecord]:
        """List run lifecycle and audit events."""
        return self._events.list_run_events(run_id, limit)

    def log_audit_event(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: dict[str, Any],
    ) -> AuditEventRecord:
        """Log an audit event to the database."""
        return self._events.log_audit_event(
            actor,
            action,
            entity_type,
            entity_id,
            details,
        )

    def list_audit_events(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEventRecord]:
        """List audit events ordered by creation time descending."""
        return self._events.list_audit_events(limit, offset)

    def list_artifacts(
        self,
        run_id: str | None = None,
        limit: int = 1000,
    ) -> list[ArtifactRecord]:
        """List registered artifacts."""
        return self._artifacts.list_artifacts(run_id, limit)

    def get_dataset(self, fingerprint: str) -> DatasetRecord | None:
        """Fetch a dataset record by fingerprint."""
        return self._catalog.get_dataset(fingerprint)

    def list_datasets(self, limit: int = 100) -> list[DatasetRecord]:
        """List registered datasets."""
        return self._catalog.list_datasets(limit)

    def list_exports(
        self,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[ExportRecord]:
        """List recorded exports."""
        return self._artifacts.list_exports(run_id, limit)

    def add_metric(
        self,
        run_id: str,
        epoch: int,
        key: str,
        value: float,
    ) -> MetricRecord:
        """Record an epoch-level training metric."""
        return self._catalog.add_metric(run_id, epoch, key, value)

    def list_metrics(
        self,
        run_id: str,
        limit: int = 1000,
    ) -> list[MetricRecord]:
        """List metrics for a run."""
        return self._catalog.list_metrics(run_id, limit)

    def add_review_queue_entry(
        self,
        entry_id: str,
        image_path: Path,
        dataset_path: Path,
        score: float,
        reason: str,
        predictions: list[dict[str, Any]],
    ) -> ReviewQueueEntry:
        """Add or update an active-learning review queue entry."""
        return self._catalog.add_review_queue_entry(
            entry_id,
            image_path,
            dataset_path,
            score,
            reason,
            predictions,
        )

    def get_review_queue_entry(self, entry_id: str) -> ReviewQueueEntry | None:
        """Fetch a review queue entry by ID."""
        return self._catalog.get_review_queue_entry(entry_id)

    def list_review_queue_entries(
        self,
        dataset_path: Path | None = None,
        status: str = "pending",
        limit: int = 100,
    ) -> list[ReviewQueueEntry]:
        """List active-learning review queue entries."""
        return self._catalog.list_review_queue_entries(dataset_path, status, limit)

    def update_review_queue_status(
        self,
        entry_id: str,
        status: str,
        corrected_labels: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Update review queue entry status and corrections."""
        return self._catalog.update_review_queue_status(
            entry_id,
            status,
            corrected_labels,
        )


__all__ = ["RunRegistry"]

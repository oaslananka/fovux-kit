"""Artifact and export persistence with filesystem metadata coordination."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from fovux.core.run_registry.events import EventStore
from fovux.core.run_registry.metadata import ArtifactMetadata, RunMetadataProvider
from fovux.core.run_registry.models import (
    ArtifactRecord,
    ExportRecord,
    _utcnow_naive,
)


class ArtifactRepository:
    """Own artifact hashing, persistence, export registration, and queries."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        metadata_provider: RunMetadataProvider,
        event_store: EventStore,
    ) -> None:
        self._session_factory = session_factory
        self._metadata_provider = metadata_provider
        self._event_store = event_store

    def _merge_artifact(
        self,
        session: Session,
        *,
        artifact_id: str,
        run_id: str | None,
        artifact_type: str,
        metadata: ArtifactMetadata,
        extra: dict[str, Any] | None,
    ) -> ArtifactRecord:
        record = ArtifactRecord(
            id=artifact_id,
            run_id=run_id,
            type=artifact_type,
            path=metadata.path,
            sha256=metadata.sha256,
            size=metadata.size,
            extra_json=json.dumps(extra or {}),
            created_at=_utcnow_naive(),
        )
        session.merge(record)
        self._event_store.append_audit_event(
            session,
            actor="system",
            action="add_artifact",
            entity_type="artifact",
            entity_id=artifact_id,
            details={"type": artifact_type, "path": metadata.path},
        )
        return record

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
        """Register or merge an artifact and its audit event atomically."""
        metadata = self._metadata_provider.artifact_metadata(
            path,
            sha256=sha256,
            size=size,
        )
        with self._session_factory() as session:
            with session.begin():
                record = self._merge_artifact(
                    session,
                    artifact_id=artifact_id,
                    run_id=run_id,
                    artifact_type=artifact_type,
                    metadata=metadata,
                    extra=extra,
                )
            return record

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
        """Write an export and associated artifact in one transaction."""
        artifact_metadata = self._metadata_provider.artifact_metadata(
            artifact_path,
            sha256=None,
            size=None,
        )
        record = ExportRecord(
            id=export_id,
            run_id=run_id,
            source_checkpoint=str(source_checkpoint.resolve()),
            artifact_path=str(artifact_path.resolve()),
            format=format,
            duration_s=duration_s,
            validation_result_json=json.dumps(validation_result or {}),
            created_at=_utcnow_naive(),
        )
        with self._session_factory() as session:
            with session.begin():
                session.add(record)
                self._merge_artifact(
                    session,
                    artifact_id=f"art_{export_id}",
                    run_id=run_id,
                    artifact_type="export",
                    metadata=artifact_metadata,
                    extra={"format": format, "duration_s": duration_s},
                )
            return record

    def list_artifacts(
        self,
        run_id: str | None = None,
        limit: int = 1000,
    ) -> list[ArtifactRecord]:
        """List registered artifacts."""
        with self._session_factory() as session:
            stmt = select(ArtifactRecord).order_by(ArtifactRecord.created_at.desc()).limit(limit)
            if run_id is not None:
                stmt = stmt.where(ArtifactRecord.run_id == run_id)
            return list(session.execute(stmt).scalars().all())

    def list_exports(
        self,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[ExportRecord]:
        """List recorded exports."""
        with self._session_factory() as session:
            stmt = select(ExportRecord).order_by(ExportRecord.created_at.desc()).limit(limit)
            if run_id is not None:
                stmt = stmt.where(ExportRecord.run_id == run_id)
            return list(session.execute(stmt).scalars().all())


__all__ = ["ArtifactRepository"]

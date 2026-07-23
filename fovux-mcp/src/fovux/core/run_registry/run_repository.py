"""Transactional command and query repository for training runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from fovux.core.run_registry.catalog_repository import CatalogRepository
from fovux.core.run_registry.events import EventStore
from fovux.core.run_registry.lifecycle import RunLifecyclePolicy, RunStatus
from fovux.core.run_registry.metadata import RunMetadata, RunMetadataProvider
from fovux.core.run_registry.models import RunRecord, _utcnow_naive


@dataclass(frozen=True, slots=True)
class RunCreateRequest:
    """Typed input shared by run creation and atomic slot reservation."""

    run_id: str
    run_path: Path
    model: str
    dataset_path: Path
    task: str
    epochs: int
    tags: list[str] | None = None
    extra: dict[str, Any] | None = None
    dataset_fingerprint: str | None = None
    config_hash: str | None = None
    code_version: str | None = None
    env_summary: str | None = None
    parent_run_id: str | None = None


class RunRepository:
    """Own run persistence, queries, and lifecycle transactions."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        metadata_provider: RunMetadataProvider,
        event_store: EventStore,
        catalog_repository: CatalogRepository,
    ) -> None:
        self._session_factory = session_factory
        self._metadata_provider = metadata_provider
        self._event_store = event_store
        self._catalog_repository = catalog_repository

    def _metadata(self, request: RunCreateRequest) -> RunMetadata:
        automatic = self._metadata_provider.build(
            model=request.model,
            dataset_path=request.dataset_path,
            task=request.task,
            epochs=request.epochs,
            extra=request.extra,
        )
        return RunMetadata(
            dataset_fingerprint=(request.dataset_fingerprint or automatic.dataset_fingerprint),
            config_hash=request.config_hash or automatic.config_hash,
            code_version=request.code_version or automatic.code_version,
            env_summary=request.env_summary or automatic.env_summary,
        )

    @staticmethod
    def _new_record(
        request: RunCreateRequest,
        metadata: RunMetadata,
    ) -> RunRecord:
        return RunRecord(
            id=request.run_id,
            run_path=str(request.run_path),
            model=request.model,
            dataset_path=str(request.dataset_path),
            task=request.task,
            epochs=request.epochs,
            status="pending",
            created_at=_utcnow_naive(),
            tags_json=json.dumps(request.tags or []),
            extra_json=json.dumps(request.extra or {}),
            dataset_fingerprint=metadata.dataset_fingerprint,
            config_hash=metadata.config_hash,
            code_version=metadata.code_version,
            env_summary=metadata.env_summary,
            parent_run_id=request.parent_run_id,
        )

    def _persist_new_run(
        self,
        session: Session,
        *,
        request: RunCreateRequest,
        record: RunRecord,
        metadata: RunMetadata,
    ) -> None:
        session.add(record)
        self._catalog_repository.register_lineage(
            session,
            run_id=request.run_id,
            model=request.model,
            dataset_path=request.dataset_path,
            task=request.task,
            dataset_fingerprint=metadata.dataset_fingerprint,
        )
        self._event_store.append_run_event(
            session,
            run_id=request.run_id,
            event_type="status_transition",
            from_status=None,
            to_status="pending",
            message="Run reserved and initialized in pending state",
        )

    def _create(
        self,
        request: RunCreateRequest,
        *,
        max_concurrent_runs: int | None,
    ) -> RunRecord:
        metadata = self._metadata(request)
        record = self._new_record(request, metadata)
        with self._session_factory() as session:
            with session.begin():
                if max_concurrent_runs is not None and max_concurrent_runs > 0:
                    active_count = (
                        session.query(RunRecord)
                        .filter(RunRecord.status.in_(["running", "pending"]))
                        .count()
                    )
                    if active_count >= max_concurrent_runs:
                        from fovux.core.errors import FovuxTrainingAlreadyRunningError

                        raise FovuxTrainingAlreadyRunningError(
                            f"Cannot start run '{request.run_id}': {active_count} "
                            f"concurrent training run(s) already active and "
                            f"max_concurrent_runs={max_concurrent_runs}."
                        )
                self._persist_new_run(
                    session,
                    request=request,
                    record=record,
                    metadata=metadata,
                )
            session.refresh(record)
            return record

    def reserve_run_slot(
        self,
        request: RunCreateRequest,
        max_concurrent_runs: int,
    ) -> RunRecord:
        """Reserve a run slot atomically, enforcing the configured active limit."""
        return self._create(request, max_concurrent_runs=max_concurrent_runs)

    def create_run(self, request: RunCreateRequest) -> RunRecord:
        """Insert a run, lineage rows, and initial event in one transaction."""
        return self._create(request, max_concurrent_runs=None)

    def get_run(self, run_id: str) -> RunRecord | None:
        """Fetch a run by ID."""
        with self._session_factory() as session:
            stmt = select(RunRecord).where(RunRecord.id == run_id)
            return session.execute(stmt).scalar_one_or_none()

    def update_status(
        self,
        run_id: str,
        status: RunStatus,
        pid: int | None = None,
    ) -> None:
        """Validate and atomically persist a run status transition."""
        with self._session_factory() as session:
            with session.begin():
                stmt = select(RunRecord).where(RunRecord.id == run_id)
                record = session.execute(stmt).scalar_one_or_none()
                if record is None:
                    return
                current_status = str(record.status)
                changed = RunLifecyclePolicy.apply(
                    record,
                    status,
                    pid=pid,
                    now=_utcnow_naive(),
                )
                if not changed:
                    return
                self._event_store.append_run_event(
                    session,
                    run_id=run_id,
                    event_type="status_transition",
                    from_status=current_status,
                    to_status=status,
                    message=(f"Run status transitioned from '{current_status}' to '{status}'"),
                )
                self._event_store.append_audit_event(
                    session,
                    actor="system",
                    action="status_transition",
                    entity_type="run",
                    entity_id=run_id,
                    details={"from": current_status, "to": status},
                )

    def list_runs(
        self,
        status: RunStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RunRecord]:
        """List runs ordered by creation time descending."""
        with self._session_factory() as session:
            stmt = (
                select(RunRecord)
                .order_by(RunRecord.created_at.desc())
                .offset(max(offset, 0))
                .limit(max(limit, 1))
            )
            if status is not None:
                stmt = stmt.where(RunRecord.status == status)
            return list(session.execute(stmt).scalars().all())

    def delete_run(self, run_id: str) -> bool:
        """Delete a run record if it exists."""
        with self._session_factory() as session:
            stmt = select(RunRecord).where(RunRecord.id == run_id)
            record = session.execute(stmt).scalar_one_or_none()
            if record is None:
                return False
            session.delete(record)
            session.commit()
            return True

    def update_tags(self, run_id: str, tags: list[str]) -> bool:
        """Replace a run's tag list."""
        with self._session_factory() as session:
            stmt = select(RunRecord).where(RunRecord.id == run_id)
            record = session.execute(stmt).scalar_one_or_none()
            if record is None:
                return False
            record.tags_json = json.dumps(tags)  # type: ignore[assignment]
            session.commit()
            return True

    def update_extra(self, run_id: str, extra: dict[str, Any]) -> bool:
        """Merge extra metadata into a run record."""
        with self._session_factory() as session:
            stmt = select(RunRecord).where(RunRecord.id == run_id)
            record = session.execute(stmt).scalar_one_or_none()
            if record is None:
                return False
            current = json.loads(str(record.extra_json or "{}"))
            if not isinstance(current, dict):
                current = {}
            current.update(extra)
            record.extra_json = json.dumps(current)  # type: ignore[assignment]
            session.commit()
            return True


__all__ = ["RunRepository"]

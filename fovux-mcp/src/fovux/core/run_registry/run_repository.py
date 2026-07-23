"""Transactional command and query repository for training runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from fovux.core.run_registry.catalog_repository import CatalogRepository
from fovux.core.run_registry.events import EventStore
from fovux.core.run_registry.lifecycle import RunLifecyclePolicy, RunStatus
from fovux.core.run_registry.metadata import RunMetadata, RunMetadataProvider
from fovux.core.run_registry.models import RunRecord, _utcnow_naive


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

    def _metadata(
        self,
        *,
        model: str,
        dataset_path: Path,
        task: str,
        epochs: int,
        extra: dict[str, Any] | None,
        dataset_fingerprint: str | None,
        config_hash: str | None,
        code_version: str | None,
        env_summary: str | None,
    ) -> RunMetadata:
        automatic = self._metadata_provider.build(
            model=model,
            dataset_path=dataset_path,
            task=task,
            epochs=epochs,
            extra=extra,
        )
        return RunMetadata(
            dataset_fingerprint=dataset_fingerprint or automatic.dataset_fingerprint,
            config_hash=config_hash or automatic.config_hash,
            code_version=code_version or automatic.code_version,
            env_summary=env_summary or automatic.env_summary,
        )

    @staticmethod
    def _new_record(
        *,
        run_id: str,
        run_path: Path,
        model: str,
        dataset_path: Path,
        task: str,
        epochs: int,
        tags: list[str] | None,
        extra: dict[str, Any] | None,
        metadata: RunMetadata,
        parent_run_id: str | None,
    ) -> RunRecord:
        return RunRecord(
            id=run_id,
            run_path=str(run_path),
            model=model,
            dataset_path=str(dataset_path),
            task=task,
            epochs=epochs,
            status="pending",
            created_at=_utcnow_naive(),
            tags_json=json.dumps(tags or []),
            extra_json=json.dumps(extra or {}),
            dataset_fingerprint=metadata.dataset_fingerprint,
            config_hash=metadata.config_hash,
            code_version=metadata.code_version,
            env_summary=metadata.env_summary,
            parent_run_id=parent_run_id,
        )

    def _persist_new_run(
        self,
        session: Session,
        *,
        record: RunRecord,
        model: str,
        dataset_path: Path,
        task: str,
        dataset_fingerprint: str,
    ) -> None:
        session.add(record)
        self._catalog_repository.register_lineage(
            session,
            run_id=str(record.id),
            model=model,
            dataset_path=dataset_path,
            task=task,
            dataset_fingerprint=dataset_fingerprint,
        )
        self._event_store.append_run_event(
            session,
            run_id=str(record.id),
            event_type="status_transition",
            from_status=None,
            to_status="pending",
            message="Run reserved and initialized in pending state",
        )

    def reserve_run_slot(
        self,
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
        """Reserve a run slot atomically, enforcing the configured active limit."""
        resolved = self._metadata(
            model=model,
            dataset_path=dataset_path,
            task=task,
            epochs=epochs,
            extra=extra,
            dataset_fingerprint=dataset_fingerprint,
            config_hash=config_hash,
            code_version=code_version,
            env_summary=env_summary,
        )
        record = self._new_record(
            run_id=run_id,
            run_path=run_path,
            model=model,
            dataset_path=dataset_path,
            task=task,
            epochs=epochs,
            tags=tags,
            extra=extra,
            metadata=resolved,
            parent_run_id=parent_run_id,
        )
        with self._session_factory() as session:
            with session.begin():
                if max_concurrent_runs > 0:
                    active_count = (
                        session.query(RunRecord)
                        .filter(RunRecord.status.in_(["running", "pending"]))
                        .count()
                    )
                    if active_count >= max_concurrent_runs:
                        from fovux.core.errors import FovuxTrainingAlreadyRunningError

                        raise FovuxTrainingAlreadyRunningError(
                            f"Cannot start run '{run_id}': {active_count} "
                            f"concurrent training run(s) already active and "
                            f"max_concurrent_runs={max_concurrent_runs}."
                        )
                self._persist_new_run(
                    session,
                    record=record,
                    model=model,
                    dataset_path=dataset_path,
                    task=task,
                    dataset_fingerprint=resolved.dataset_fingerprint,
                )
            session.refresh(record)
            return record

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
        """Insert a run, lineage rows, and initial event in one transaction."""
        resolved = self._metadata(
            model=model,
            dataset_path=dataset_path,
            task=task,
            epochs=epochs,
            extra=extra,
            dataset_fingerprint=dataset_fingerprint,
            config_hash=config_hash,
            code_version=code_version,
            env_summary=env_summary,
        )
        record = self._new_record(
            run_id=run_id,
            run_path=run_path,
            model=model,
            dataset_path=dataset_path,
            task=task,
            epochs=epochs,
            tags=tags,
            extra=extra,
            metadata=resolved,
            parent_run_id=parent_run_id,
        )
        with self._session_factory() as session:
            with session.begin():
                self._persist_new_run(
                    session,
                    record=record,
                    model=model,
                    dataset_path=dataset_path,
                    task=task,
                    dataset_fingerprint=resolved.dataset_fingerprint,
                )
            session.refresh(record)
            return record

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

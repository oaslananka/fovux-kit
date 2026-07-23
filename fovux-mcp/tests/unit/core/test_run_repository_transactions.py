"""Transactional behavior and legacy compatibility for the run repository."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from fovux.core.run_registry.catalog_repository import CatalogRepository
from fovux.core.run_registry.database import RegistryDatabase
from fovux.core.run_registry.events import EventStore
from fovux.core.run_registry.metadata import RunMetadataProvider
from fovux.core.run_registry.models import AuditEventRecord, RunRecord
from fovux.core.run_registry.run_repository import RunCreateRequest, RunRepository


class FailingAuditEventStore(EventStore):
    """Force an audit append failure inside the caller's transaction."""

    @staticmethod
    def append_audit_event(
        session: Session,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: dict[str, object],
    ) -> AuditEventRecord:
        del session, actor, action, entity_type, entity_id, details
        raise RuntimeError("audit unavailable")


def _repository(
    database: RegistryDatabase,
    *,
    event_store: EventStore | None = None,
) -> tuple[RunRepository, EventStore]:
    metadata = RunMetadataProvider()
    events = event_store or EventStore(database.session_factory)
    catalog = CatalogRepository(database.session_factory, metadata)
    return (
        RunRepository(
            database.session_factory,
            metadata_provider=metadata,
            event_store=events,
            catalog_repository=catalog,
        ),
        events,
    )


def test_status_and_transition_events_roll_back_together(tmp_path: Path) -> None:
    database = RegistryDatabase(tmp_path / "runs.db")
    repository, events = _repository(database)
    try:
        repository.create_run(
            RunCreateRequest(
                run_id="run_tx",
                run_path=tmp_path / "run_tx",
                model="yolo.pt",
                dataset_path=tmp_path / "dataset",
                task="detect",
                epochs=1,
            )
        )
        repository.update_status("run_tx", "running")
        failing_repository, _ = _repository(
            database,
            event_store=FailingAuditEventStore(database.session_factory),
        )

        with pytest.raises(RuntimeError, match="audit unavailable"):
            failing_repository.update_status("run_tx", "complete")

        record = repository.get_run("run_tx")
        assert record is not None
        assert record.status == "running"
        assert [event.to_status for event in events.list_run_events("run_tx")] == [
            "running",
            "pending",
        ]
    finally:
        database.close()


def test_pre_v1_runs_table_is_migrated_without_losing_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE runs (
                id VARCHAR PRIMARY KEY,
                status VARCHAR NOT NULL,
                model VARCHAR NOT NULL,
                dataset_path VARCHAR NOT NULL,
                task VARCHAR NOT NULL,
                epochs INTEGER NOT NULL,
                created_at VARCHAR NOT NULL,
                started_at VARCHAR,
                finished_at VARCHAR,
                pid INTEGER,
                run_path VARCHAR NOT NULL,
                tags_json TEXT NOT NULL,
                extra_json TEXT NOT NULL
            );
            INSERT INTO runs (
                id, status, model, dataset_path, task, epochs, created_at,
                started_at, finished_at, pid, run_path, tags_json, extra_json
            ) VALUES (
                'legacy-run', 'complete', 'legacy.pt', '/dataset', 'detect', 2,
                '2026-01-01T00:00:00.000000', NULL, NULL, NULL,
                '/runs/legacy-run', '[]', '{}'
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    database = RegistryDatabase(db_path)
    repository, _ = _repository(database)
    try:
        record = repository.get_run("legacy-run")
        assert record is not None
        assert record.model == "legacy.pt"
        assert record.dataset_fingerprint is None
        assert record.parent_run_id is None
    finally:
        database.close()


def test_update_extra_handles_missing_and_legacy_non_mapping_values(tmp_path: Path) -> None:
    database = RegistryDatabase(tmp_path / "runs.db")
    repository, _ = _repository(database)
    try:
        assert repository.update_extra("missing", {"new": True}) is False
        repository.create_run(
            RunCreateRequest(
                run_id="legacy-extra",
                run_path=tmp_path / "legacy-extra",
                model="yolo.pt",
                dataset_path=tmp_path / "dataset",
                task="detect",
                epochs=1,
            )
        )
        with database.session_factory() as session:
            record = session.get(RunRecord, "legacy-extra")
            assert record is not None
            record.extra_json = "[]"
            session.commit()

        assert repository.update_extra("legacy-extra", {"new": True}) is True
        updated = repository.get_run("legacy-extra")
        assert updated is not None
        assert json.loads(str(updated.extra_json)) == {"new": True}
    finally:
        database.close()

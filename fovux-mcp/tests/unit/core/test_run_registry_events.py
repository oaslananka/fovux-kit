"""Focused tests for durable registry event ordering."""

from __future__ import annotations

import json
from pathlib import Path

from fovux.core.run_registry.database import RegistryDatabase
from fovux.core.run_registry.events import EventStore


def test_operation_events_keep_durable_id_order(tmp_path: Path) -> None:
    database = RegistryDatabase(tmp_path / "runs.db")
    store = EventStore(database.session_factory)
    try:
        first = store.create_operation_event("op", "status_change", {"status": "pending"})
        second = store.create_operation_event("op", "status_change", {"status": "running"})

        assert [event.id for event in store.list_operation_events()] == [
            first.id,
            second.id,
        ]
        assert [event.id for event in store.list_operation_events(last_event_id=int(first.id))] == [
            second.id
        ]
        assert json.loads(str(second.data_json)) == {"status": "running"}
    finally:
        database.close()


def test_audit_events_preserve_descending_query_order(tmp_path: Path) -> None:
    database = RegistryDatabase(tmp_path / "runs.db")
    store = EventStore(database.session_factory)
    try:
        first = store.log_audit_event("system", "first", "run", "run-1", {})
        second = store.log_audit_event("system", "second", "run", "run-1", {})

        assert [event.id for event in store.list_audit_events()] == [
            second.id,
            first.id,
        ]
    finally:
        database.close()

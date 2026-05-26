"""Unit tests for fovux.core.runs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import text

from fovux.core.runs import RunRegistry, close_registry, get_registry


@pytest.fixture()
def registry(tmp_path: Path) -> RunRegistry:
    """Return a fresh in-memory RunRegistry backed by a temp DB."""
    return RunRegistry(tmp_path / "test_runs.db")


def test_create_and_get_run(registry: RunRegistry, tmp_path: Path) -> None:
    """create_run + get_run should round-trip."""
    registry.create_run(
        run_id="run_test_001",
        run_path=tmp_path / "runs" / "run_test_001",
        model="yolov8n.pt",
        dataset_path=tmp_path / "data",
        task="detect",
        epochs=10,
        tags=["test"],
    )
    record = registry.get_run("run_test_001")
    assert record is not None
    assert record.id == "run_test_001"
    assert record.model == "yolov8n.pt"
    assert record.status == "pending"
    assert record.epochs == 10


def test_sqlite_wal_pragmas_are_enabled(tmp_path: Path) -> None:
    """Registry connections should use WAL-friendly pragmas for live metric reads."""
    registry = RunRegistry(tmp_path / "wal_runs.db")

    with registry._engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar_one()
        synchronous = conn.execute(text("PRAGMA synchronous")).scalar_one()
        foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar_one()

    assert journal_mode == "wal"
    assert synchronous == 1
    assert foreign_keys == 1


def test_get_run_not_found(registry: RunRegistry) -> None:
    """get_run for unknown ID should return None."""
    assert registry.get_run("nonexistent") is None


def test_update_status(registry: RunRegistry, tmp_path: Path) -> None:
    """update_status should change the run's status."""
    registry.create_run(
        run_id="run_status_test",
        run_path=tmp_path / "runs" / "run_status_test",
        model="yolov8n.pt",
        dataset_path=tmp_path / "data",
        task="detect",
        epochs=5,
    )
    registry.update_status("run_status_test", "running", pid=12345)
    record = registry.get_run("run_status_test")
    assert record is not None
    assert record.status == "running"
    assert record.pid == 12345
    assert record.started_at is not None


def test_update_status_complete_sets_finished_at(registry: RunRegistry, tmp_path: Path) -> None:
    """Completing a run should set finished_at."""
    registry.create_run(
        run_id="run_complete_test",
        run_path=tmp_path / "runs" / "run_complete_test",
        model="yolov8n.pt",
        dataset_path=tmp_path / "data",
        task="detect",
        epochs=5,
    )
    registry.update_status("run_complete_test", "complete")
    record = registry.get_run("run_complete_test")
    assert record is not None
    assert record.finished_at is not None


def test_list_runs_empty(registry: RunRegistry) -> None:
    """list_runs on empty DB should return empty list."""
    assert registry.list_runs() == []


def test_list_runs_filter_by_status(registry: RunRegistry, tmp_path: Path) -> None:
    """list_runs should correctly filter by status."""
    registry.create_run(
        run_id="run_a",
        run_path=tmp_path / "run_a",
        model="yolov8n.pt",
        dataset_path=tmp_path / "data",
        task="detect",
        epochs=5,
    )
    registry.create_run(
        run_id="run_b",
        run_path=tmp_path / "run_b",
        model="yolov8n.pt",
        dataset_path=tmp_path / "data",
        task="detect",
        epochs=5,
    )
    registry.update_status("run_a", "complete")
    pending = registry.list_runs(status="pending")
    complete = registry.list_runs(status="complete")
    assert len(pending) == 1
    assert len(complete) == 1
    assert pending[0].id == "run_b"
    assert complete[0].id == "run_a"


def test_list_runs_supports_offset(registry: RunRegistry, tmp_path: Path) -> None:
    """list_runs should honor offset so callers can paginate large histories."""
    for run_id in ("run_a", "run_b", "run_c"):
        registry.create_run(
            run_id=run_id,
            run_path=tmp_path / run_id,
            model="yolov8n.pt",
            dataset_path=tmp_path / "data",
            task="detect",
            epochs=5,
        )

    first_page = registry.list_runs(limit=1, offset=0)
    second_page = registry.list_runs(limit=1, offset=1)

    assert len(first_page) == 1
    assert len(second_page) == 1
    assert first_page[0].id != second_page[0].id


def test_delete_run(registry: RunRegistry, tmp_path: Path) -> None:
    """delete_run should remove the record."""
    registry.create_run(
        run_id="run_del",
        run_path=tmp_path / "run_del",
        model="yolov8n.pt",
        dataset_path=tmp_path / "data",
        task="detect",
        epochs=3,
    )
    assert registry.delete_run("run_del") is True
    assert registry.get_run("run_del") is None


def test_delete_run_not_found(registry: RunRegistry) -> None:
    """delete_run for unknown ID should return False."""
    assert registry.delete_run("ghost") is False


def test_update_tags_replaces_tags(registry: RunRegistry, tmp_path: Path) -> None:
    """update_tags should persist a replacement tag list."""
    registry.create_run(
        run_id="run_tags",
        run_path=tmp_path / "run_tags",
        model="yolov8n.pt",
        dataset_path=tmp_path / "data",
        task="detect",
        epochs=3,
        tags=["old"],
    )

    assert registry.update_tags("run_tags", ["edge", "baseline"]) is True
    record = registry.get_run("run_tags")

    assert record is not None
    assert record.tags_json == '["edge", "baseline"]'
    assert registry.update_tags("ghost", ["missing"]) is False


def test_get_registry_reuses_singleton_for_same_path(tmp_path: Path) -> None:
    """get_registry should cache one registry per database path."""
    db_path = tmp_path / "singleton.db"

    first = get_registry(db_path)
    second = get_registry(db_path)

    assert first is second
    close_registry(db_path)


def test_get_registry_is_thread_safe(tmp_path: Path) -> None:
    """Concurrent singleton lookups should all return the same instance."""
    db_path = tmp_path / "thread-safe.db"

    with ThreadPoolExecutor(max_workers=8) as executor:
        registries = list(executor.map(lambda _: get_registry(db_path), range(16)))

    assert len({id(registry) for registry in registries}) == 1
    close_registry(db_path)


def test_close_registry_drops_cached_instance(tmp_path: Path) -> None:
    """close_registry should evict the cached registry instance."""
    db_path = tmp_path / "evict.db"

    first = get_registry(db_path)
    close_registry(db_path)
    second = get_registry(db_path)

    assert first is not second
    close_registry(db_path)

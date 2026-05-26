"""SQLite-backed run registry.

Tracks all training runs: metadata, status, metrics pointers.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy import (
    event as sa_event,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

_REGISTRIES: dict[Path, RunRegistry] = {}
_REGISTRIES_LOCK = threading.Lock()

RunStatus = Literal["pending", "running", "complete", "failed", "stopped", "archived"]


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class RunRecord(Base):
    """ORM model for a training run row."""

    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    status = Column(String, nullable=False, default="pending")
    model = Column(String, nullable=False)
    dataset_path = Column(String, nullable=False)
    task = Column(String, nullable=False, default="detect")
    epochs = Column(Integer, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    pid = Column(Integer, nullable=True)
    run_path = Column(String, nullable=False)
    tags_json = Column(Text, nullable=False, default="[]")
    extra_json = Column(Text, nullable=False, default="{}")


class RunRegistry:
    """CRUD interface for the SQLite runs registry.

    Args:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize and create tables if needed."""
        self._engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            poolclass=NullPool,
            connect_args={"check_same_thread": False},
        )

        @sa_event.listens_for(self._engine, "connect")
        def _set_sqlite_pragmas(
            dbapi_conn: sqlite3.Connection,
            _connection_record: object,
        ) -> None:
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA synchronous=NORMAL")
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine, expire_on_commit=False)

    def close(self) -> None:
        """Dispose the SQLite engine and release pooled connections."""
        self._engine.dispose()

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
    ) -> RunRecord:
        """Insert a new run record.

        Args:
            run_id: Unique run identifier.
            run_path: Path to the run directory.
            model: Model name or path.
            dataset_path: Path to the dataset.
            task: YOLO task (detect, segment, classify, pose, obb).
            epochs: Total training epochs.
            tags: Optional list of user tags.
            extra: Optional extra metadata dict.

        Returns:
            The newly created RunRecord.
        """
        with self._Session() as session:
            record = RunRecord(
                id=run_id,
                run_path=str(run_path),
                model=model,
                dataset_path=str(dataset_path),
                task=task,
                epochs=epochs,
                status="pending",
                created_at=datetime.now(UTC).replace(tzinfo=None),
                tags_json=json.dumps(tags or []),
                extra_json=json.dumps(extra or {}),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def get_run(self, run_id: str) -> RunRecord | None:
        """Fetch a run by ID.

        Args:
            run_id: The run identifier.

        Returns:
            RunRecord or None if not found.
        """
        with self._Session() as session:
            stmt = select(RunRecord).where(RunRecord.id == run_id)
            return session.execute(stmt).scalar_one_or_none()

    def update_status(
        self,
        run_id: str,
        status: RunStatus,
        pid: int | None = None,
    ) -> None:
        """Update run status and optionally pid.

        Args:
            run_id: The run identifier.
            status: New status value.
            pid: Process ID of the training subprocess (if applicable).
        """
        with self._Session() as session:
            stmt = select(RunRecord).where(RunRecord.id == run_id)
            record = session.execute(stmt).scalar_one_or_none()
            if record is None:
                return
            record.status = status  # type: ignore[assignment]
            if pid is not None:
                record.pid = pid  # type: ignore[assignment]
            if status == "running" and record.started_at is None:
                record.started_at = datetime.now(UTC).replace(tzinfo=None)
            if status in ("complete", "failed", "stopped", "archived"):
                record.finished_at = datetime.now(UTC).replace(tzinfo=None)  # type: ignore[assignment]
            session.commit()

    def list_runs(
        self,
        status: RunStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RunRecord]:
        """List runs, optionally filtered by status.

        Args:
            status: Filter by this status if provided.
            limit: Maximum number of results.
            offset: Number of results to skip before returning rows.

        Returns:
            List of RunRecord objects ordered by created_at desc.
        """
        with self._Session() as session:
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
        """Delete a run record.

        Args:
            run_id: The run identifier.

        Returns:
            True if deleted, False if not found.
        """
        with self._Session() as session:
            stmt = select(RunRecord).where(RunRecord.id == run_id)
            record = session.execute(stmt).scalar_one_or_none()
            if record is None:
                return False
            session.delete(record)
            session.commit()
            return True

    def update_tags(self, run_id: str, tags: list[str]) -> bool:
        """Replace a run's tag list."""
        with self._Session() as session:
            stmt = select(RunRecord).where(RunRecord.id == run_id)
            record = session.execute(stmt).scalar_one_or_none()
            if record is None:
                return False
            record.tags_json = json.dumps(tags)  # type: ignore[assignment]
            session.commit()
            return True

    def update_extra(self, run_id: str, extra: dict[str, Any]) -> bool:
        """Merge extra metadata into a run record."""
        with self._Session() as session:
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

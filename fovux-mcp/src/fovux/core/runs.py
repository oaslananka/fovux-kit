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


class OperationRecord(Base):
    """ORM model for a background operation."""

    __tablename__ = "operations"

    id = Column(String, primary_key=True)
    idempotency_key = Column(String, nullable=True, unique=True, index=True)
    tool = Column(String, nullable=False)
    arguments_json = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending")
    progress = Column(Integer, nullable=True)
    result_json = Column(Text, nullable=True)
    error_type = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    run_id = Column(String, nullable=True)


class OperationEventRecord(Base):
    """ORM model for operation lifecycle events (for SSE resume)."""

    __tablename__ = "operation_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operation_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # status_change, progress, etc.
    data_json = Column(Text, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )


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
    ) -> RunRecord:
        """Reserve a run slot atomically, locking the DB if concurrent limit is set."""
        with self._Session() as session:
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

    def create_operation(
        self,
        op_id: str,
        tool: str,
        arguments: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> OperationRecord:
        """Insert a new operation record."""
        with self._Session() as session:
            record = OperationRecord(
                id=op_id,
                tool=tool,
                arguments_json=json.dumps(arguments),
                idempotency_key=idempotency_key,
                status="pending",
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def get_operation(self, op_id: str) -> OperationRecord | None:
        """Fetch an operation by ID."""
        with self._Session() as session:
            stmt = select(OperationRecord).where(OperationRecord.id == op_id)
            return session.execute(stmt).scalar_one_or_none()

    def get_operation_by_idempotency_key(self, idempotency_key: str) -> OperationRecord | None:
        """Fetch an operation by idempotency key."""
        with self._Session() as session:
            stmt = select(OperationRecord).where(OperationRecord.idempotency_key == idempotency_key)
            return session.execute(stmt).scalar_one_or_none()

    def update_operation_status(
        self,
        op_id: str,
        status: str,
        error_type: str | None = None,
        error: str | None = None,
        result: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> None:
        """Update operation status, timestamps, results/errors."""
        with self._Session() as session:
            stmt = select(OperationRecord).where(OperationRecord.id == op_id)
            record = session.execute(stmt).scalar_one_or_none()
            if record is None:
                return
            record.status = status  # type: ignore[assignment]
            if status == "running" and record.started_at is None:
                record.started_at = datetime.now(UTC).replace(tzinfo=None)
            elif status in ("succeeded", "failed", "cancelled"):
                record.finished_at = datetime.now(UTC).replace(tzinfo=None)  # type: ignore[assignment]
            if error_type is not None:
                record.error_type = error_type  # type: ignore[assignment]
            if error is not None:
                record.error = error  # type: ignore[assignment]
            if result is not None:
                record.result_json = json.dumps(result)  # type: ignore[assignment]
            if run_id is not None:
                record.run_id = run_id  # type: ignore[assignment]
            session.commit()

    def update_operation_progress(self, op_id: str, progress: int) -> None:
        """Update progress percentage of an operation."""
        with self._Session() as session:
            stmt = select(OperationRecord).where(OperationRecord.id == op_id)
            record = session.execute(stmt).scalar_one_or_none()
            if record is None:
                return
            record.progress = progress  # type: ignore[assignment]
            session.commit()

    def list_operations(self, limit: int = 100) -> list[OperationRecord]:
        """List operations ordered by created_at desc."""
        with self._Session() as session:
            stmt = select(OperationRecord).order_by(OperationRecord.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars().all())

    def create_operation_event(
        self,
        op_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> OperationEventRecord:
        """Create and persist a lifecycle event for an operation."""
        with self._Session() as session:
            event_rec = OperationEventRecord(
                operation_id=op_id,
                event_type=event_type,
                data_json=json.dumps(data),
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            session.add(event_rec)
            session.commit()
            session.refresh(event_rec)
            return event_rec

    def list_operation_events(
        self,
        last_event_id: int | None = None,
        limit: int = 1000,
    ) -> list[OperationEventRecord]:
        """List operation events newer than last_event_id."""
        with self._Session() as session:
            stmt = select(OperationEventRecord).order_by(OperationEventRecord.id.asc()).limit(limit)
            if last_event_id is not None:
                stmt = stmt.where(OperationEventRecord.id > last_event_id)
            return list(session.execute(stmt).scalars().all())


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

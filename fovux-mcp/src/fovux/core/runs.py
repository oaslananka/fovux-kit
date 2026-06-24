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
    Float,
    Integer,
    String,
    Text,
    create_engine,
    select,
    text,
)
from sqlalchemy import (
    event as sa_event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.types import TypeDecorator

_REGISTRIES: dict[Path, RunRegistry] = {}
_REGISTRIES_LOCK = threading.Lock()

RunStatus = Literal["pending", "running", "complete", "failed", "stopped", "archived"]


def _utcnow_naive() -> datetime:
    """Return a naive UTC datetime for registry ORM objects."""
    return datetime.now(UTC).replace(tzinfo=None)


def _serialize_datetime(value: datetime) -> str:
    """Serialize datetimes explicitly instead of relying on sqlite3 adapters."""
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.isoformat(timespec="microseconds")


def _deserialize_datetime(value: str | datetime) -> datetime:
    """Deserialize registry datetimes stored as explicit ISO-8601 strings."""
    if isinstance(value, datetime):
        return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed


class UtcDateTime(TypeDecorator[datetime]):
    """Store datetimes as ISO-8601 text to avoid sqlite3 default adapters."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: datetime | None, _dialect: object) -> str | None:
        """Serialize a Python datetime before binding it to SQLite."""
        if value is None:
            return None
        return _serialize_datetime(value)

    def process_result_value(
        self, value: str | datetime | None, _dialect: object
    ) -> datetime | None:
        """Deserialize a stored SQLite value into a Python datetime."""
        if value is None:
            return None
        return _deserialize_datetime(value)


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
        UtcDateTime,
        nullable=False,
        default=_utcnow_naive,
    )
    started_at = Column(UtcDateTime, nullable=True)
    finished_at = Column(UtcDateTime, nullable=True)
    pid = Column(Integer, nullable=True)
    run_path = Column(String, nullable=False)
    tags_json = Column(Text, nullable=False, default="[]")
    extra_json = Column(Text, nullable=False, default="{}")

    # Experiment intelligence / lineage tracking metadata
    dataset_fingerprint = Column(String, nullable=True)
    config_hash = Column(String, nullable=True)
    code_version = Column(String, nullable=True)
    env_summary = Column(Text, nullable=True)
    parent_run_id = Column(String, nullable=True)


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
        UtcDateTime,
        nullable=False,
        default=_utcnow_naive,
    )
    started_at = Column(UtcDateTime, nullable=True)
    finished_at = Column(UtcDateTime, nullable=True)
    run_id = Column(String, nullable=True)


class OperationEventRecord(Base):
    """ORM model for operation lifecycle events (for SSE resume)."""

    __tablename__ = "operation_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operation_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # status_change, progress, etc.
    data_json = Column(Text, nullable=False)
    created_at = Column(
        UtcDateTime,
        nullable=False,
        default=_utcnow_naive,
    )


class SchemaMigrationRecord(Base):
    """ORM model for schema migrations."""

    __tablename__ = "schema_migrations"

    version = Column(Integer, primary_key=True)
    applied_at = Column(
        UtcDateTime,
        nullable=False,
        default=_utcnow_naive,
    )


class RunEventRecord(Base):
    """ORM model for run lifecycle events (status transition, artifact creation, etc.)."""

    __tablename__ = "run_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, nullable=True, index=True)
    event_type = Column(String, nullable=False)  # status_transition, artifact_created, audit, etc.
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(
        UtcDateTime,
        nullable=False,
        default=_utcnow_naive,
    )
    extra_json = Column(Text, nullable=False, default="{}")


class DatasetRecord(Base):
    """ORM model for datasets."""

    __tablename__ = "datasets"

    fingerprint = Column(String, primary_key=True)
    path = Column(String, nullable=False)
    class_map_json = Column(Text, nullable=False, default="{}")
    created_at = Column(
        UtcDateTime,
        nullable=False,
        default=_utcnow_naive,
    )
    extra_json = Column(Text, nullable=False, default="{}")


class ArtifactRecord(Base):
    """ORM model for artifacts (e.g. checkpoints, exports, datasets)."""

    __tablename__ = "artifacts"

    id = Column(String, primary_key=True)
    run_id = Column(String, nullable=True, index=True)
    type = Column(String, nullable=False)  # e.g., checkpoint, dataset, export
    path = Column(String, nullable=False)
    sha256 = Column(String, nullable=True)
    size = Column(Integer, nullable=True)
    created_at = Column(
        UtcDateTime,
        nullable=False,
        default=_utcnow_naive,
    )
    extra_json = Column(Text, nullable=False, default="{}")


class ModelRecord(Base):
    """ORM model for registered or downloaded models."""

    __tablename__ = "models"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    task = Column(String, nullable=False)
    path = Column(String, nullable=True)
    sha256 = Column(String, nullable=True)
    created_at = Column(
        UtcDateTime,
        nullable=False,
        default=_utcnow_naive,
    )


class ExportRecord(Base):
    """ORM model for model exports."""

    __tablename__ = "exports"

    id = Column(String, primary_key=True)
    run_id = Column(String, nullable=True, index=True)
    source_checkpoint = Column(String, nullable=False)
    artifact_path = Column(String, nullable=False)
    format = Column(String, nullable=False)
    duration_s = Column(Float, nullable=True)
    validation_result_json = Column(Text, nullable=True)
    created_at = Column(
        UtcDateTime,
        nullable=False,
        default=_utcnow_naive,
    )


class ReviewQueueEntry(Base):
    """ORM model for active learning review queue entries."""

    __tablename__ = "review_queue"

    id: Any = Column(String, primary_key=True)
    image_path: Any = Column(String, nullable=False)
    dataset_path: Any = Column(String, nullable=False)
    score: Any = Column(Float, nullable=False)
    reason: Any = Column(String, nullable=False)
    status: Any = Column(String, nullable=False, default="pending")
    predictions_json: Any = Column(Text, nullable=False, default="[]")
    corrected_labels_json: Any = Column(Text, nullable=True)
    created_at: Any = Column(
        UtcDateTime,
        nullable=False,
        default=_utcnow_naive,
    )


class MetricRecord(Base):
    """ORM model for step or epoch-level metrics."""

    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, nullable=False, index=True)
    epoch = Column(Integer, nullable=False)
    metric_key = Column(String, nullable=False)
    metric_value = Column(Float, nullable=False)
    created_at = Column(
        UtcDateTime,
        nullable=False,
        default=_utcnow_naive,
    )


class TagRecord(Base):
    """ORM model for entity tags."""

    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String, nullable=False)  # run, artifact, dataset
    entity_id = Column(String, nullable=False)
    tag = Column(String, nullable=False)


class AuditEventRecord(Base):
    """ORM model for security/system audit events."""

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    created_at = Column(
        UtcDateTime,
        nullable=False,
        default=_utcnow_naive,
    )
    details_json = Column(Text, nullable=False, default="{}")


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
        self._run_migrations()
        self._Session = sessionmaker(bind=self._engine, expire_on_commit=False)

    def _run_migrations(self) -> None:
        """Ensure schema migrations are executed, adding columns if needed."""
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "version INTEGER PRIMARY KEY,"
                    "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            row = conn.execute(text("SELECT MAX(version) FROM schema_migrations")).fetchone()
            current_version = row[0] if row and row[0] is not None else 0

        if current_version < 1:
            self._apply_migration_1()

    def _apply_migration_1(self) -> None:
        """Add columns to runs table for dataset/config tracking."""
        with self._engine.begin() as conn:
            res = conn.execute(text("PRAGMA table_info(runs)")).fetchall()
            existing_cols = {r[1] for r in res}

            new_cols = {
                "dataset_fingerprint": "TEXT",
                "config_hash": "TEXT",
                "code_version": "TEXT",
                "env_summary": "TEXT",
                "parent_run_id": "TEXT",
            }

            for col_name, col_type in new_cols.items():
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE runs ADD COLUMN {col_name} {col_type}"))

            conn.execute(
                text(
                    "INSERT OR IGNORE INTO schema_migrations (version, applied_at) "
                    "VALUES (1, :applied_at)"
                ),
                {"applied_at": _serialize_datetime(_utcnow_naive())},
            )

    def close(self) -> None:
        """Dispose the SQLite engine and release pooled connections."""
        self._engine.dispose()

    def _auto_metadata(
        self,
        model: str,
        dataset_path: Path,
        task: str,
        epochs: int,
        extra: dict[str, Any] | None = None,
    ) -> tuple[str, str, str, str]:
        """Automatically calculate metadata fields if they are None."""
        import hashlib

        from fovux import __version__ as fovux_version

        # 1. Dataset Fingerprint
        try:
            from fovux.core.dataset_config import _find_yolo_yaml

            yaml_path = _find_yolo_yaml(dataset_path)
            content = yaml_path.read_bytes()
            dataset_fingerprint = hashlib.sha256(content).hexdigest()
        except Exception:
            dataset_fingerprint = hashlib.sha256(
                str(dataset_path.resolve()).encode("utf-8")
            ).hexdigest()

        # 2. Config Hash
        payload = {
            "model": model,
            "dataset_path": str(dataset_path.resolve()),
            "epochs": epochs,
            "task": task,
            "extra": extra or {},
        }
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        config_hash = hashlib.sha256(encoded).hexdigest()

        # 3. Code Version
        code_version = fovux_version

        # 4. Env Summary
        import platform
        import sys

        summary: dict[str, Any] = {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        }
        try:
            import torch  # type: ignore[import-not-found]

            summary["torch_version"] = torch.__version__
            summary["cuda_available"] = torch.cuda.is_available()
        except ImportError:
            summary["torch_version"] = "not_installed"
            summary["cuda_available"] = False
        env_summary = json.dumps(summary)

        return dataset_fingerprint, config_hash, code_version, env_summary

    def _register_lineage(
        self,
        session: Session,
        run_id: str,
        model: str,
        dataset_path: Path,
        task: str,
        dataset_fingerprint: str,
    ) -> None:
        """Internal helper to populate datasets and models tables for lineage tracking."""
        # 1. Dataset Registration
        try:
            from fovux.core.dataset_utils import read_yolo_data_yaml

            data = read_yolo_data_yaml(dataset_path)
            class_map = data.get("names", {})
        except Exception:
            class_map = {}

        db_dataset = session.get(DatasetRecord, dataset_fingerprint)
        if db_dataset is None:
            db_dataset = DatasetRecord(
                fingerprint=dataset_fingerprint,
                path=str(dataset_path.resolve()),
                class_map_json=json.dumps(class_map),
            )
            session.merge(db_dataset)

        # 2. Model Registration
        model_name = Path(model).name
        db_model = session.get(ModelRecord, model_name)
        if db_model is None:
            db_model = ModelRecord(
                id=model_name,
                name=model_name,
                task=task,
                path=model,
            )
            session.merge(db_model)

        # 3. Status Transition Event to Pending
        event = RunEventRecord(
            run_id=run_id,
            event_type="status_transition",
            from_status=None,
            to_status="pending",
            message="Run reserved and initialized in pending state",
        )
        session.add(event)

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
        """Reserve a run slot atomically, locking the DB if concurrent limit is set."""
        auto_fp, auto_ch, auto_cv, auto_env = self._auto_metadata(
            model, dataset_path, task, epochs, extra
        )
        dataset_fingerprint = dataset_fingerprint or auto_fp
        config_hash = config_hash or auto_ch
        code_version = code_version or auto_cv
        env_summary = env_summary or auto_env

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
                    created_at=_utcnow_naive(),
                    tags_json=json.dumps(tags or []),
                    extra_json=json.dumps(extra or {}),
                    dataset_fingerprint=dataset_fingerprint,
                    config_hash=config_hash,
                    code_version=code_version,
                    env_summary=env_summary,
                    parent_run_id=parent_run_id,
                )
                session.add(record)
                self._register_lineage(
                    session, run_id, model, dataset_path, task, dataset_fingerprint
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
            dataset_fingerprint: Optional fingerprint of dataset.
            config_hash: Optional hash of config.
            code_version: Optional code version.
            env_summary: Optional system environment summary.
            parent_run_id: Optional parent run/checkpoint reference.

        Returns:
            The newly created RunRecord.
        """
        auto_fp, auto_ch, auto_cv, auto_env = self._auto_metadata(
            model, dataset_path, task, epochs, extra
        )
        dataset_fingerprint = dataset_fingerprint or auto_fp
        config_hash = config_hash or auto_ch
        code_version = code_version or auto_cv
        env_summary = env_summary or auto_env

        with self._Session() as session:
            with session.begin():
                record = RunRecord(
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
                    dataset_fingerprint=dataset_fingerprint,
                    config_hash=config_hash,
                    code_version=code_version,
                    env_summary=env_summary,
                    parent_run_id=parent_run_id,
                )
                session.add(record)
                self._register_lineage(
                    session, run_id, model, dataset_path, task, dataset_fingerprint
                )
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

            current_status = str(record.status)
            if current_status != status:
                valid_targets = {
                    "pending": {"running", "complete", "failed", "stopped", "archived"},
                    "running": {"complete", "failed", "stopped", "archived"},
                    "complete": {"running", "archived"},
                    "failed": {"running", "archived"},
                    "stopped": {"running", "archived"},
                    "archived": {"pending", "running"},
                }
                if status not in valid_targets.get(current_status, set()):
                    raise ValueError(
                        f"Invalid run status transition from '{current_status}' to '{status}'"
                    )

                # Log status transition event
                event = RunEventRecord(
                    run_id=run_id,
                    event_type="status_transition",
                    from_status=current_status,
                    to_status=status,
                    message=f"Run status transitioned from '{current_status}' to '{status}'",
                )
                session.add(event)

                # Log audit event
                audit = AuditEventRecord(
                    actor="system",
                    action="status_transition",
                    entity_type="run",
                    entity_id=run_id,
                    details_json=json.dumps({"from": current_status, "to": status}),
                )
                session.add(audit)

            record.status = status  # type: ignore[assignment]
            if pid is not None:
                record.pid = pid  # type: ignore[assignment]
            if status == "running" and record.started_at is None:
                record.started_at = _utcnow_naive()
            if status in ("complete", "failed", "stopped", "archived"):
                record.finished_at = _utcnow_naive()  # type: ignore[assignment]
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
                created_at=_utcnow_naive(),
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
                record.started_at = _utcnow_naive()
            elif status in ("succeeded", "failed", "cancelled"):
                record.finished_at = _utcnow_naive()  # type: ignore[assignment]
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
                created_at=_utcnow_naive(),
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
        """Register or merge a new artifact record."""
        import hashlib

        path_str = str(path.resolve())
        if path.exists() and path.is_file():
            if size is None:
                size = path.stat().st_size
            if sha256 is None:
                h = hashlib.sha256()
                try:
                    with path.open("rb") as f:
                        for chunk in iter(lambda: f.read(65536), b""):
                            h.update(chunk)
                    sha256 = h.hexdigest()
                except Exception:
                    sha256 = None

        with self._Session() as session:
            record = ArtifactRecord(
                id=artifact_id,
                run_id=run_id,
                type=artifact_type,
                path=path_str,
                sha256=sha256,
                size=size,
                extra_json=json.dumps(extra or {}),
                created_at=_utcnow_naive(),
            )
            session.merge(record)

            # Log audit event
            audit = AuditEventRecord(
                actor="system",
                action="add_artifact",
                entity_type="artifact",
                entity_id=artifact_id,
                details_json=json.dumps({"type": artifact_type, "path": path_str}),
            )
            session.add(audit)
            session.commit()
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
        """Record a model export and associate it with a corresponding artifact."""
        with self._Session() as session:
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
            session.add(record)
            session.commit()

        # Also register the export file as an artifact
        self.add_artifact(
            artifact_id=f"art_{export_id}",
            run_id=run_id,
            artifact_type="export",
            path=artifact_path,
            extra={"format": format, "duration_s": duration_s},
        )
        return record

    def list_run_events(self, run_id: str | None = None, limit: int = 1000) -> list[RunEventRecord]:
        """List run lifecycle and audit events."""
        with self._Session() as session:
            stmt = select(RunEventRecord).order_by(RunEventRecord.created_at.desc()).limit(limit)
            if run_id is not None:
                stmt = stmt.where(RunEventRecord.run_id == run_id)
            return list(session.execute(stmt).scalars().all())

    def log_audit_event(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: dict[str, Any],
    ) -> AuditEventRecord:
        """Log an audit event to the database."""
        with self._Session() as session:
            record = AuditEventRecord(
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details_json=json.dumps(details),
                created_at=_utcnow_naive(),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def list_audit_events(self, limit: int = 100, offset: int = 0) -> list[AuditEventRecord]:
        """List audit events ordered by created_at desc."""
        with self._Session() as session:
            stmt = (
                select(AuditEventRecord)
                .order_by(AuditEventRecord.created_at.desc())
                .offset(max(offset, 0))
                .limit(max(limit, 1))
            )
            return list(session.execute(stmt).scalars().all())

    def list_artifacts(self, run_id: str | None = None, limit: int = 1000) -> list[ArtifactRecord]:
        """List registered artifacts."""
        with self._Session() as session:
            stmt = select(ArtifactRecord).order_by(ArtifactRecord.created_at.desc()).limit(limit)
            if run_id is not None:
                stmt = stmt.where(ArtifactRecord.run_id == run_id)
            return list(session.execute(stmt).scalars().all())

    def get_dataset(self, fingerprint: str) -> DatasetRecord | None:
        """Fetch a dataset record by fingerprint."""
        with self._Session() as session:
            return session.get(DatasetRecord, fingerprint)

    def list_datasets(self, limit: int = 100) -> list[DatasetRecord]:
        """List registered datasets."""
        with self._Session() as session:
            stmt = select(DatasetRecord).order_by(DatasetRecord.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars().all())

    def list_exports(self, run_id: str | None = None, limit: int = 100) -> list[ExportRecord]:
        """List recorded exports."""
        with self._Session() as session:
            stmt = select(ExportRecord).order_by(ExportRecord.created_at.desc()).limit(limit)
            if run_id is not None:
                stmt = stmt.where(ExportRecord.run_id == run_id)
            return list(session.execute(stmt).scalars().all())

    def add_metric(self, run_id: str, epoch: int, key: str, value: float) -> MetricRecord:
        """Record an epoch-level training metric."""
        with self._Session() as session:
            record = MetricRecord(
                run_id=run_id,
                epoch=epoch,
                metric_key=key,
                metric_value=value,
                created_at=_utcnow_naive(),
            )
            session.add(record)
            session.commit()
            return record

    def list_metrics(self, run_id: str, limit: int = 1000) -> list[MetricRecord]:
        """List metrics for a run."""
        with self._Session() as session:
            stmt = (
                select(MetricRecord)
                .where(MetricRecord.run_id == run_id)
                .order_by(MetricRecord.epoch.asc(), MetricRecord.created_at.asc())
                .limit(limit)
            )
            return list(session.execute(stmt).scalars().all())

    def add_review_queue_entry(
        self,
        entry_id: str,
        image_path: Path,
        dataset_path: Path,
        score: float,
        reason: str,
        predictions: list[dict[str, Any]],
    ) -> ReviewQueueEntry:
        """Add or update an active learning review queue entry."""
        with self._Session() as session:
            record = ReviewQueueEntry(
                id=entry_id,
                image_path=str(image_path.resolve()),
                dataset_path=str(dataset_path.resolve()),
                score=score,
                reason=reason,
                status="pending",
                predictions_json=json.dumps(predictions),
                created_at=_utcnow_naive(),
            )
            session.merge(record)
            session.commit()
            return record

    def get_review_queue_entry(self, entry_id: str) -> ReviewQueueEntry | None:
        """Fetch a review queue entry by ID."""
        with self._Session() as session:
            return session.get(ReviewQueueEntry, entry_id)

    def list_review_queue_entries(
        self,
        dataset_path: Path | None = None,
        status: str = "pending",
        limit: int = 100,
    ) -> list[ReviewQueueEntry]:
        """List active learning review queue entries ordered by score desc."""
        with self._Session() as session:
            stmt = (
                select(ReviewQueueEntry)
                .where(ReviewQueueEntry.status == status)
                .order_by(ReviewQueueEntry.score.desc())
                .limit(limit)
            )
            if dataset_path is not None:
                stmt = stmt.where(ReviewQueueEntry.dataset_path == str(dataset_path.resolve()))
            return list(session.execute(stmt).scalars().all())

    def update_review_queue_status(
        self,
        entry_id: str,
        status: str,
        corrected_labels: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Update review queue entry status and corrections."""
        with self._Session() as session:
            record = session.get(ReviewQueueEntry, entry_id)
            if record is None:
                return False
            record.status = status
            if corrected_labels is not None:
                record.corrected_labels_json = json.dumps(corrected_labels)
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

"""SQLAlchemy schema for the local run registry."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


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


__all__ = [
    "ArtifactRecord",
    "AuditEventRecord",
    "Base",
    "DatasetRecord",
    "ExportRecord",
    "MetricRecord",
    "ModelRecord",
    "OperationEventRecord",
    "OperationRecord",
    "ReviewQueueEntry",
    "RunEventRecord",
    "RunRecord",
    "SchemaMigrationRecord",
    "TagRecord",
    "UtcDateTime",
    "_deserialize_datetime",
    "_serialize_datetime",
    "_utcnow_naive",
]

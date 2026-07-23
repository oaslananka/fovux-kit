"""Persistence and lifecycle queries for background operations."""

from __future__ import annotations

import json
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from fovux.core.run_registry.lifecycle import OperationLifecyclePolicy, OperationStatus
from fovux.core.run_registry.models import OperationRecord, _utcnow_naive


class OperationRepository:
    """Own background-operation state and query persistence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_operation(
        self,
        op_id: str,
        tool: str,
        arguments: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> OperationRecord:
        """Insert a new operation record."""
        with self._session_factory() as session:
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
        with self._session_factory() as session:
            stmt = select(OperationRecord).where(OperationRecord.id == op_id)
            return session.execute(stmt).scalar_one_or_none()

    def get_operation_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> OperationRecord | None:
        """Fetch an operation by idempotency key."""
        with self._session_factory() as session:
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
        """Validate and persist operation status, result, and error fields."""
        with self._session_factory() as session:
            with session.begin():
                stmt = select(OperationRecord).where(OperationRecord.id == op_id)
                record = session.execute(stmt).scalar_one_or_none()
                if record is None:
                    return
                OperationLifecyclePolicy.apply(
                    record,
                    cast(OperationStatus, status),
                    now=_utcnow_naive(),
                )
                if error_type is not None:
                    record.error_type = error_type  # type: ignore[assignment]
                if error is not None:
                    record.error = error  # type: ignore[assignment]
                if result is not None:
                    record.result_json = json.dumps(result)  # type: ignore[assignment]
                if run_id is not None:
                    record.run_id = run_id  # type: ignore[assignment]

    def update_operation_progress(self, op_id: str, progress: int) -> None:
        """Update progress percentage of an operation."""
        with self._session_factory() as session:
            stmt = select(OperationRecord).where(OperationRecord.id == op_id)
            record = session.execute(stmt).scalar_one_or_none()
            if record is None:
                return
            record.progress = progress  # type: ignore[assignment]
            session.commit()

    def list_operations(self, limit: int = 100) -> list[OperationRecord]:
        """List operations ordered by creation time descending."""
        with self._session_factory() as session:
            stmt = select(OperationRecord).order_by(OperationRecord.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars().all())


__all__ = ["OperationRepository"]

"""Durable run, operation, and audit event persistence."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from fovux.core.run_registry.models import (
    AuditEventRecord,
    OperationEventRecord,
    RunEventRecord,
    _utcnow_naive,
)


class EventStore:
    """Append and query durable registry events."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def append_run_event(
        session: Session,
        *,
        run_id: str | None,
        event_type: str,
        from_status: str | None,
        to_status: str | None,
        message: str | None,
        extra: dict[str, Any] | None = None,
    ) -> RunEventRecord:
        """Append a run event to the caller's active transaction."""
        record = RunEventRecord(
            run_id=run_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            message=message,
            created_at=_utcnow_naive(),
            extra_json=json.dumps(extra or {}),
        )
        session.add(record)
        return record

    @staticmethod
    def append_audit_event(
        session: Session,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: dict[str, Any],
    ) -> AuditEventRecord:
        """Append an audit event to the caller's active transaction."""
        record = AuditEventRecord(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details_json=json.dumps(details),
            created_at=_utcnow_naive(),
        )
        session.add(record)
        return record

    def create_operation_event(
        self,
        op_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> OperationEventRecord:
        """Create and commit one lifecycle event for an operation."""
        with self._session_factory() as session:
            record = OperationEventRecord(
                operation_id=op_id,
                event_type=event_type,
                data_json=json.dumps(data),
                created_at=_utcnow_naive(),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def list_operation_events(
        self,
        last_event_id: int | None = None,
        limit: int = 1000,
    ) -> list[OperationEventRecord]:
        """List operation events newer than an optional durable event ID."""
        with self._session_factory() as session:
            stmt = select(OperationEventRecord).order_by(OperationEventRecord.id.asc()).limit(limit)
            if last_event_id is not None:
                stmt = stmt.where(OperationEventRecord.id > last_event_id)
            return list(session.execute(stmt).scalars().all())

    def list_run_events(
        self,
        run_id: str | None = None,
        limit: int = 1000,
    ) -> list[RunEventRecord]:
        """List run lifecycle events using the existing descending time order."""
        with self._session_factory() as session:
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
        """Create and commit one standalone audit event."""
        with self._session_factory() as session:
            record = self.append_audit_event(
                session,
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
            )
            session.commit()
            session.refresh(record)
            return record

    def list_audit_events(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEventRecord]:
        """List audit events ordered by creation time descending."""
        with self._session_factory() as session:
            stmt = (
                select(AuditEventRecord)
                .order_by(AuditEventRecord.created_at.desc())
                .offset(max(offset, 0))
                .limit(max(limit, 1))
            )
            return list(session.execute(stmt).scalars().all())


__all__ = ["EventStore"]

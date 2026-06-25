"""Structured audit event schema helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

AUDIT_SCHEMA_VERSION = "fovux.audit.v1"


def build_audit_details(
    *,
    tool_id: str,
    run_id: str | None,
    status: str,
    risk_level: str,
    policy_mode: str,
    paths: list[str],
    challenge_id: object | None = None,
    error: str | None = None,
    duration_seconds: float | None = None,
    approval_reason: object | None = None,
) -> dict[str, Any]:
    """Return canonical audit details shared by tools, listings, and bundles."""
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "tool_id": tool_id,
        "run_id": run_id,
        "principal": "client",
        "session_id": None,
        "scopes": [],
        "resolved_target_paths": paths,
        "policy_mode": policy_mode,
        "risk_level": risk_level,
        "challenge_id": challenge_id,
        "result": {"status": status, "error": error},
        "duration_seconds": duration_seconds,
        "redaction_status": "redacted",
        "approval": {"required": approval_reason is not None, "reason": approval_reason},
        "status": status,
        "error": error,
    }


def audit_timeline_summary(*, action: str, details: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact activity-timeline item for Studio."""
    result = details.get("result") if isinstance(details.get("result"), dict) else {}
    return {
        "title": action,
        "status": result.get("status", details.get("status", "unknown")),
        "tool_id": details.get("tool_id", action),
        "run_id": details.get("run_id"),
        "risk_level": details.get("risk_level", "unknown"),
        "policy_mode": details.get("policy_mode", "unknown"),
        "redaction_status": details.get("redaction_status", "redacted"),
    }


def normalize_audit_record(record: Any) -> dict[str, Any]:  # noqa: ANN401
    """Normalize an ORM audit row to the canonical export/listing schema."""
    raw = json.loads(str(getattr(record, "details_json", None) or "{}"))
    details = raw if isinstance(raw, dict) else {}
    details.setdefault("schema_version", AUDIT_SCHEMA_VERSION)
    details.setdefault("tool_id", getattr(record, "action", None))
    details.setdefault("run_id", None)
    details.setdefault("principal", getattr(record, "actor", "client"))
    details.setdefault("session_id", None)
    details.setdefault("scopes", [])
    details.setdefault("resolved_target_paths", [])
    details.setdefault("policy_mode", "unknown")
    details.setdefault("risk_level", "unknown")
    details.setdefault("challenge_id", None)
    details.setdefault(
        "result", {"status": details.get("status", "unknown"), "error": details.get("error")}
    )
    details.setdefault("duration_seconds", None)
    details.setdefault("redaction_status", "redacted")
    return {
        "id": getattr(record, "id", None),
        "actor": getattr(record, "actor", None),
        "action": getattr(record, "action", None),
        "entity_type": getattr(record, "entity_type", None),
        "entity_id": getattr(record, "entity_id", None),
        "created_at": record.created_at.isoformat() + "Z"
        if getattr(record, "created_at", None)
        else None,
        "details": details,
        "timeline": audit_timeline_summary(
            action=str(getattr(record, "action", "unknown")), details=details
        ),
    }

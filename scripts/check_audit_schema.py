"""Fail-fast checks for the structured local activity event schema."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP_ROOT = ROOT / "fovux-mcp"
SRC = MCP_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fovux.core.audit import AUDIT_SCHEMA_VERSION, build_audit_details  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    details = build_audit_details(
        tool_id="model_list",
        run_id=None,
        status="success",
        risk_level="read_only",
        policy_mode="developer",
        paths=[],
    )
    for field in [
        "schema_version",
        "tool_id",
        "run_id",
        "principal",
        "session_id",
        "scopes",
        "resolved_target_paths",
        "policy_mode",
        "risk_level",
        "challenge_id",
        "result",
        "duration_seconds",
        "redaction_status",
    ]:
        if field not in details:
            failures.append(f"Audit details missing field: {field}")
    if AUDIT_SCHEMA_VERSION != "fovux.audit.v1":
        failures.append("Unexpected audit schema version")
    bundles = _read(MCP_ROOT / "src" / "fovux" / "tools" / "bundles.py")
    for phrase in [
        "normalize_audit_record",
        "audit_schema_version",
        "recent_audit_events",
    ]:
        if phrase not in bundles:
            failures.append(f"Bundle/listing code missing phrase: {phrase}")
    docs = _read(ROOT / "docs" / "audit-event-schema.md")
    for phrase in [
        "schema_version",
        "tool_id",
        "principal",
        "scopes",
        "policy_mode",
        "challenge_id",
        "duration_seconds",
        "recent_audit_events",
    ]:
        if phrase not in docs:
            failures.append(f"Audit schema docs missing phrase: {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "Audit schema checks passed: canonical details, list/export usage, and docs are aligned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Structured Audit Event Schema

Fovux writes local activity events to `FOVUX_HOME/runs.db` and exposes the same normalized schema through
`list_audit_events` and support bundles.

## Schema fields

| Field | Purpose |
| --- | --- |
| `schema_version` | Current schema marker, `fovux.audit.v1`. |
| `tool_id` | MCP/backend tool identifier. |
| `run_id` | Run identifier when the event is tied to a run. |
| `principal` | Local caller category, currently `client` or `policy`. |
| `session_id` | Session identifier when available. |
| `scopes` | Token scopes considered for the call. |
| `resolved_target_paths` | Redacted/resolved local paths touched by the action. |
| `policy_mode` | Active policy mode at execution time. |
| `risk_level` | Tool risk category from HTTP policy metadata. |
| `challenge_id` | Human approval challenge identifier when applicable. |
| `result` | Structured status and error summary. |
| `duration_seconds` | Tool lifecycle duration when available. |
| `redaction_status` | Redaction state for exported event details. |

## Studio activity timeline

Each normalized event also includes a compact `timeline` object with title, status, tool id, run id,
risk level, policy mode, and redaction status. Studio can render this directly in an activity timeline
without parsing raw database rows.

## Retention and export

The local database is the retention source for current events. Support bundles include the latest 100
normalized events under `recent_audit_events` with `audit_schema_version`, so support exports and the
`list_audit_events` tool use the same schema.

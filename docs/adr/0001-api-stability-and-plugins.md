# ADR 0001: API Stability and Plugin Boundaries

## Status

Accepted for the 2.0 planning track.

## Context

Fovux exposes several public-ish surfaces: CLI commands, MCP tools and schemas, Studio command IDs,
local HTTP API routes, config files, generated artifacts, and docs. A future plugin or SDK layer must not
turn every internal module into a stable API by accident.

## Decision

Fovux 2.0 treats these as versioned public boundaries:

- CLI command names, flags, exit-code behavior, and machine-readable JSON output.
- MCP tool names, input schemas, output schemas, annotations, policy scopes, and error categories.
- Studio command IDs, contributed views, webview message contracts, and package manifest contribution IDs.
- Local HTTP API routes used by Studio, authentication requirements, and stable response fields.
- Config files, generated run/export artifacts, bundles, and registry records documented for users.

Fovux treats these as internal unless explicitly documented: Python module internals, React component props,
private helper functions, temporary file layouts, and test fixtures.

## Semver policy

- Patch: bug fixes, docs, additive optional fields, non-breaking validation improvements.
- Minor: additive tools, additive output fields, new Studio commands, new optional config keys.
- Major: removed tools, renamed fields, stricter required inputs, incompatible artifact/config migration.

Tool schema snapshots are the compatibility gate. Breaking changes require a migration note and 2.0 milestone.

## Plugin capability model

Plugins may be introduced only behind explicit capabilities: read workspace, read datasets, write datasets,
start training, export artifacts, network access, and hosted integration access. Risky capabilities require
human confirmation, audit events, and least-privilege policy scopes. Plugins must not bypass local-first,
no-telemetry defaults, Workspace Trust restrictions, or HTTP auth.

## 1.x to 2.0 migration checklist

- Document every breaking CLI/MCP/HTTP/Studio/config/artifact change.
- Provide schema diff and example before/after payloads.
- Provide config and artifact migration instructions.
- Keep compatibility shims where feasible for one minor release.
- Update docs, tool snapshots, Studio LM tool mappings, and release notes in the same PR.

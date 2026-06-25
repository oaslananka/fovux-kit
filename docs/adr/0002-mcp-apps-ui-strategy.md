# ADR 0002: MCP Apps and Interactive UI Strategy

## Status

Accepted as a product discovery decision for 2026-06-25.

## Context

MCP Apps and interactive in-chat UI patterns are emerging. Claude and other hosts are moving beyond text-only
tool results toward embedded forms, dashboards, and visual workflows. Fovux already has a VS Code extension
with trusted workspace integration, local file access, command palette entries, webviews, and a no-telemetry
local-first posture.

## Decision

Defer MCP Apps as a primary UI surface. Keep Fovux Studio as the primary professional UI for dataset review,
training, export, benchmarking, and local file workflows. Track MCP Apps as an experimental bridge only for
read-only summaries and lightweight review workflows until host support, permissions, packaging, and security
semantics are stable enough for local computer-vision operations.

## Rationale

- Fovux Studio has stronger control over local files, Workspace Trust, command enablement, extension release
  evidence, and offline operation.
- MCP Apps could be useful for small interactive cards, read-only dashboards, or review queues inside chat.
- Dataset editing, training launch, export, and file writes require local trust boundaries and human approval.
- A rushed MCP Apps UI could duplicate Studio and weaken security guarantees.

## Reconsideration signals

Review this decision by 2026-12-31 or earlier if all are true:

1. At least two major hosts support interactive MCP UI with documented permission and persistence semantics.
2. The UI surface supports local-only operation without hosted uploads.
3. Fovux can enforce Workspace Trust-equivalent restrictions.
4. Fovux can snapshot-test the UI contract and audit all write actions.
5. Users request chat-native review workflows that Studio cannot satisfy.

## Next experiment

A future prototype may expose a read-only MCP Apps dashboard that mirrors Fovux Studio run summaries and
benchmark cards. It must not start training, write labels, export models, or upload data.

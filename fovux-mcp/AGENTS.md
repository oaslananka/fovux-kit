# Fovux MCP Backend Instructions

These instructions apply to `fovux-mcp/**` and supplement the root instructions.

## Boundary

This package owns the Python domain/core, CLI, MCP stdio server, loopback HTTP/SSE API, tool registry, policy/challenge behavior, run registry, dataset/model operations, training/evaluation/export/inference and local audit state.

Treat filesystem, process execution, model files, datasets, network streams, HTTP requests and MCP tool arguments as untrusted inputs.

## MCP and HTTP authority

- Stdio MCP and the Studio HTTP API are separate transports over the same underlying product/tool contract.
- The HTTP service remains loopback-only by default.
- Preserve bearer-token validation, rate limiting, policy modes, per-tool allowlist/scope, confirmation/challenge semantics, timeout/concurrency bounds and audit events.
- Do not treat CORS or loopback binding as a replacement for the bearer-token/tool-policy contract.
- Do not expose raw bearer tokens or full sensitive tool payloads in logs/audit events.

## Tool registry contract

A tool change may require updates to:

- implementation under `src/fovux/tools/**`;
- registry/manifest metadata;
- schemas;
- policy/effect metadata;
- generated docs;
- Studio LM-tool mappings;
- tests.

Do not bypass registry/policy enforcement by calling a mutating implementation directly from a transport.

## Filesystem and process safety

- Use canonical path-policy helpers for read/write/delete/import/export operations.
- Preserve path traversal/symlink and workspace/home containment semantics.
- Use structured subprocess argument lists. Do not interpolate untrusted values through a shell.
- Bound subprocess duration/output where the operation contract provides limits.
- Secure-file helpers must retain safe creation/permission behavior.

## ML/product truth

- Training, evaluation, inference, benchmark and export output must reflect actual executed runs.
- Do not fabricate accuracy, latency, device compatibility, quantization quality, dataset integrity or deployment suitability.
- GPU/accelerator availability must be detected, not assumed.
- Keep reproducibility metadata and run lineage consistent when resuming, comparing, tagging, archiving or exporting runs.

## Persistence and audit

Run registry/audit records are evidence.

- Preserve transactional/atomic behavior where the repository relies on it.
- Do not silently discard failed operations or rewrite historical evidence to simplify cleanup.
- Audit records must avoid raw secrets and excessive private payloads.

## Verification

Run focused unit tests first. Changes to tools/policy/HTTP normally also require:

```text
uv run pytest
uv run mypy --strict --warn-unused-ignores src/fovux
uv run ruff check .
uv run ruff format --check .
uv run python ../scripts/check_tool_contracts.py
python ../scripts/check_agent_policy.py
python ../scripts/check_http_security_policy.py
```

Use slow/network/GPU/security lanes when the changed behavior requires them.

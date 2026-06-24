# ADR 0004 — MCP stdio vs Fovux Studio Local API

## Status

Accepted on 2026-06-24.

## Context

The MCP 2025-06-18 transport specification defines two standard transports:

1. stdio; and
2. Streamable HTTP.

Streamable HTTP is not a generic REST API. It requires a single MCP endpoint that supports JSON-RPC
POST/GET semantics, `Accept: application/json, text/event-stream`, optional SSE response streams,
`Mcp-Session-Id` lifecycle semantics, and `MCP-Protocol-Version` handling.

Fovux currently has two separate surfaces:

- the FastMCP stdio server used by MCP clients; and
- `fovux-mcp serve --http`, a FastAPI REST/SSE surface used by Fovux Studio dashboards, guarded tool
  calls, run state, and metric streams.

The existing `serve --http` route set exposes `/health`, `/runs`, `/runs/{id}/stream`, `/tools/{name}`,
and related Studio endpoints. It is not the single JSON-RPC MCP endpoint required by Streamable HTTP.

## Decision

Keep `fovux-mcp` stdio as the supported MCP transport for this release train.

Keep `fovux-mcp serve --http` for backwards-compatible Studio integration, but name it the
**Fovux Studio local API** or **custom REST/SSE bridge** everywhere in current documentation, CLI help,
and conformance material.

Do not expose an official `/mcp` Streamable HTTP endpoint until a dedicated implementation includes
protocol conformance tests for:

- JSON-RPC `initialize`, `tools/list`, and `tools/call` over one MCP endpoint;
- HTTP POST and GET behavior;
- `Accept` and `Content-Type` negotiation;
- `Mcp-Session-Id` lifecycle behavior;
- `MCP-Protocol-Version` handling;
- `Origin` validation, localhost binding, and authentication;
- backwards compatibility with the Studio local API.

## Consequences

- MCP clients should configure Fovux through stdio.
- Studio continues to use the local API without route or command breakage.
- The local API remains bearer-token protected, local-first, and explicitly custom.
- Public docs must not describe `serve --http` as official MCP Streamable HTTP.
- A future `/mcp` endpoint, if added, must be separate from or carefully layered over the Studio API
  and must ship with conformance tests before being advertised.

## Backwards compatibility plan

- Keep the `--http` flag and existing REST/SSE routes for Fovux Studio.
- Keep token, session-token, policy, rate-limit, challenge, and audit behavior unchanged.
- Update help text and docs only; do not break existing Studio settings or command invocations.
- If official Streamable HTTP is added later, document migration from Studio local API URLs to the
  MCP endpoint separately.

## Validation

The repository enforces this decision with:

```bash
python scripts/check_mcp_transport_decision.py
python scripts/quality_gate.py mcp-docs
```

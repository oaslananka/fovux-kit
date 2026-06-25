# ADR 0006: Studio Local API Auth Model

## Status

Accepted

## Context

The Fovux Studio local API can launch training, inference, and export tools. In v1.0.0 it trusted any local process that could reach loopback.

## Decision

Fovux requires a bearer token for every Studio local API route except `/health`. The token is persisted under `FOVUX_HOME/auth.token` and read directly by the VS Code extension. Requests that include an untrusted browser `Origin` are rejected with `403 Forbidden` before tool execution.

## Consequences

- The Studio local API becomes safe for same-machine local use.
- Studio and `fovux-mcp` must share the same `FOVUX_HOME`.
- Clients that previously used unauthenticated curl snippets must add the bearer token.
- Non-local bind hosts require explicit `--allow-nonlocal-bind`; this is not a remote-server auth model.
- Remote or multi-user deployments require a separate OAuth/OIDC resource-server design before support is advertised.

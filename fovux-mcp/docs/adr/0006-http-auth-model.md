# ADR 0006: HTTP Auth Model

## Status

Accepted

## Context

The optional HTTP transport can launch training, inference, and export tools. In v1.0.0 it trusted any local process that could reach loopback.

## Decision

Fovux v2.0.0 requires a bearer token for every HTTP route except `/health`. The token is persisted under `FOVUX_HOME/auth.token` and read directly by the VS Code extension.

## Consequences

- The HTTP transport becomes safe for same-machine local use.
- Studio and `fovux-mcp` must share the same `FOVUX_HOME`.
- Clients that previously used unauthenticated curl snippets must add the bearer token.

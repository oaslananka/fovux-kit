# ADR 0008: Central Tool Registry

## Status

Accepted

## Context

v1.0.0 kept HTTP tool exposure and MCP registration logic in separate import paths. This duplicated tool lists and made it easy for the transports to drift apart.

## Decision

Fovux v2.0.0 introduces `fovux.core.tool_registry` as the canonical map from tool name to callable. MCP registration and HTTP proxy resolution now share this registry.

## Consequences

- one source of truth for tool exposure
- less boilerplate in `server.py` and HTTP proxy code
- easier future work for tracing, OpenAPI generation, and policy enforcement

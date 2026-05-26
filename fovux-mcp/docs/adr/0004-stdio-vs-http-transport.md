# ADR 0004 — stdio vs HTTP Transport

## Decision

Use stdio for MCP and local HTTP for Studio.

## Why

- MCP clients expect stdio-first ergonomics
- Studio needs a web-friendly polling and SSE surface
- Both can share the same filesystem state cleanly

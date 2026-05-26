# ADR 0002 — SQLite Runs Registry

## Decision

Track runs in SQLite rather than scanning directories for every query.

## Why

- Fast run listing for Studio and HTTP
- Stable metadata for status, pid, and timestamps
- Good enough durability without external services

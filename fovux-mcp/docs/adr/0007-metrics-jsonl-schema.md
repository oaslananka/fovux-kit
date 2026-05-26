# ADR 0007: metrics.jsonl as the Streaming Source of Truth

## Status

Accepted

## Context

`results.csv` is useful for batch inspection but awkward for real-time streaming:

- column names drift with upstream versions
- the file must be fully re-read to derive deltas
- it is only flushed on epoch boundaries

## Decision

The detached worker writes `metrics.jsonl` directly with a stable per-line schema. The HTTP SSE stream uses it preferentially and falls back to CSV only for older runs.

## Consequences

- Studio receives normalized metric payloads
- delta streaming becomes offset-based instead of O(n) file scans
- older runs remain readable without migration

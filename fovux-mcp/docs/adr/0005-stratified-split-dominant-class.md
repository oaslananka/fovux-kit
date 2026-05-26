# ADR 0005 — Stratified Split by Dominant Class

## Decision

Use dominant-class heuristics for the current YOLO split implementation.

## Why

- Simple and deterministic
- Good enough for v1.0.0 local workflows
- Keeps split generation predictable without adding a heavy multi-label dependency

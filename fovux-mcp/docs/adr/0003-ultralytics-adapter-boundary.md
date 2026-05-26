# ADR 0003 — Ultralytics Adapter Boundary

## Decision

Keep all Ultralytics imports behind `core/ultralytics_adapter.py`.

## Why

- Limits breakage when upstream APIs drift
- Centralizes compatibility fixes
- Keeps tool modules focused on Fovux behavior

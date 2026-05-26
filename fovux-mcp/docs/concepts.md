# Concepts

## FOVUX_HOME

Fovux stores all local state under `~/.fovux/` by default, or under `FOVUX_HOME` when explicitly set.

## Runs

A run is a directory plus a registry row. It includes:

- `params.json` with launch parameters
- `status.json` with lifecycle state
- `results.csv` or `metrics.jsonl` with training metrics
- weights, logs, reports, and exported artifacts

## Models

Models are discovered from:

- `~/.fovux/models/`
- per-run directories under `~/.fovux/runs/`

The `model_list` tool merges both views.

## Dataset Formats

Fovux v1.0.0 primarily targets YOLO-format workflows. COCO support exists for selected tools such as inspection and conversion. Unsupported format paths return explicit `FovuxDatasetFormatError` responses.

## HTTP vs MCP

- MCP over stdio is the primary automation interface.
- Local HTTP is the Studio integration layer.
- Both operate on the same filesystem state, not on shared in-memory state.

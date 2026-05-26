# Fovux MCP

**From dataset to deployed ONNX, in one conversation.**

Fovux MCP is the local Python server behind the Fovux workflow. It exposes MCP tools covering:

- dataset inspection, validation, duplicate detection, conversion, and splitting
- non-blocking YOLO training lifecycle management
- evaluation, per-class reporting, and error analysis
- export, quantization, inference, and latency benchmarking
- run and model comparison for day-to-day iteration

## What Makes Fovux Different

- Local-first by default: no SaaS account, no cloud lock-in, no hidden control plane
- Built for edge-CV practitioners, not generic automation demos
- File-oriented state under `~/.fovux/` so runs, exports, and reports stay portable
- Designed to pair with MCP clients and with the Fovux Studio VS Code extension

## Start Here

1. Read [Getting Started](getting-started.md) for the 5-minute tour.
2. Learn the core mental model in [Concepts](concepts.md).
3. Jump to [Tool Reference](tools/dataset_inspect.md) for exact inputs, outputs, and examples.

## Availability

Fovux is currently installed from source from this repository. The documentation in this directory is the canonical reference for the current release.

# Performance Guide

Fovux v2.0.0 focuses on predictable local performance for long-running YOLO workflows.

## Metric streaming

The Studio dashboard now prefers `metrics.jsonl` written directly by the worker. The HTTP stream no longer re-parses the full history every polling tick. Instead:

- a snapshot is sent on connect
- file changes are watched
- only appended rows are streamed after the snapshot

This keeps steady-state CPU usage low for active dashboards.

## Dataset inspection

Large datasets benefit from stable mtimes and cached filesystem metadata. When repeatedly inspecting the same dataset:

- keep labels under a consistent root
- avoid rewriting annotation files unnecessarily
- prefer SSD-backed `FOVUX_HOME` for cache-heavy workflows

## Duplicate detection

Perceptual hashing is CPU-bound. For the fastest runs:

- store input images on local disk instead of network storage
- avoid background antivirus scans over the dataset root
- run duplicate scans before opening multiple heavy dashboard sessions

## RTSP inference

The RTSP path now uses reconnect backoff and a bounded capture queue. For stable streams:

- keep `CAP_PROP_BUFFERSIZE=1`
- prefer streams that report FPS correctly
- write outputs to a fast local disk when recording

## Benchmarking

Use `benchmark_latency` after export or quantization to compare checkpoints in the same environment. Small ONNX and INT8 wins are meaningful only when measured on the target hardware profile.

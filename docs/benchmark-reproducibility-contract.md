# Benchmark Reproducibility Contract

`benchmark_latency` must produce repeatable evidence that can be compared across commits, hardware, and exported artifacts.

## Required output

- Warmup count and measured iteration count.
- p50, p95, p99, mean, standard deviation, throughput, and peak memory.
- Input shape and batch size.
- Environment context: Python version, platform, processor, backend, device, threads, and NumPy version.
- Artifact context: path, name, suffix, byte size, and SHA-256 digest.
- Baseline comparison when `baseline_path` points to a JSON file with `latency_p95_ms`.
- Reproducibility notes explaining that warmups are excluded and p95 comparisons detect regressions.

## Regression rule

A benchmark is marked as a regression when current p95 latency is more than 10% above the baseline p95.

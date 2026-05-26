# Recipe 03 — Quantize For Edge

1. Export a baseline artifact with `export_onnx` or `export_tflite`.
2. Run `quantize_int8` with a representative calibration set.
3. Compare size and accuracy with `quantize_report`.
4. Benchmark the winning artifact with `benchmark_latency`.

Use this when the deployment question is not “can I quantize?” but “should I ship this quantized build?”

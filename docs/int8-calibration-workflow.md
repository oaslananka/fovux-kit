# INT8 Calibration Workflow

INT8 can reduce latency and model size, but bad calibration can reduce accuracy. Fovux treats INT8 as a guarded workflow.

## Required flow

1. Use a representative YOLO dataset with `data.yaml` for calibration.
2. Run `quantize_int8` with `calibration_dataset`; the tool rejects datasets with too few images.
3. Run `quantize_report` on the original and quantized artifacts to compare mAP50 and size.
4. Run `benchmark_latency` on both artifacts to compare p95 latency and throughput.
5. Use `deployment_advise` for target-specific caveats before promoting the artifact.

## Guardrails

- Calibration data is required for INT8 export.
- Accuracy drop above `max_map50_drop` is a regression.
- Strict mode fails the report when the accuracy drop exceeds tolerance.
- Next steps for unacceptable drops: increase calibration diversity, lower quantization aggressiveness, keep FP16/FP32, or choose another runtime.
- Studio export targets must explain INT8 tradeoffs for Raspberry Pi, Android/TFLite, Edge TPU, Jetson/TensorRT, and CPU-only targets.

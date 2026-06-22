# deployment_advise

Analyze deployment readiness, preflight checks, parity, and benchmarks.

## Inputs

- `model_path`
- `target_profile`
- `dataset_path`
- `imgsz`

## Outputs

- target_profile
- model_path
- format
- model_size_mb
- compatibility_preflight
- quantization_recommendation
- readiness_score
- parity_check
- benchmark_results
- risk_warnings
- runtime_snippets
- report_path

## Examples

```json
{"model_path":"~/exports/best.onnx","target_profile":"raspberry_pi"}
{"model_path":"~/exports/model.tflite","target_profile":"android_tflite","dataset_path":"~/data"}
```

## Common Errors

- unknown checkpoint or model path

## Related Tools

`export_onnx`, `export_tflite`, `benchmark_latency`, `quantize_int8`

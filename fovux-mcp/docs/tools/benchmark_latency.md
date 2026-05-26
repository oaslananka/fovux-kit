# benchmark_latency

Measure local inference latency and throughput for a model artifact.

## Inputs

- `model_path`
- `backend`
- `device`
- `imgsz`, `batch_size`
- `num_warmup`, `num_iterations`, `threads`

## Outputs

- latency percentiles, mean, stddev
- throughput FPS
- peak memory

## Examples

```json
{"model_path":"~/exports/run_demo.onnx"}
{"model_path":"~/exports/retail.tflite","backend":"tflite","num_iterations":50}
{"model_path":"~/models/factory.pt","backend":"pytorch","device":"cpu"}
```

## Common Errors

- missing model artifact
- unsupported backend on the current machine

## Related Tools

`export_onnx`, `export_tflite`, `quantize_report`

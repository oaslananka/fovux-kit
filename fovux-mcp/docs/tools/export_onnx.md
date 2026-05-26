# export_onnx

Export a checkpoint to ONNX and optionally verify parity.

## Inputs

- `checkpoint`
- `output_path`
- `imgsz`, `opset`
- `dynamic`, `simplify`, `half`, `device`
- `parity_check`, `parity_tolerance`

## Outputs

- ONNX output path
- model size and export duration
- parity metrics

## Examples

```json
{"checkpoint":"run_demo"}
{"checkpoint":"~/models/retail.pt","output_path":"~/exports/retail.onnx"}
{"checkpoint":"~/models/factory.pt","dynamic":true,"parity_tolerance":0.001}
```

## Common Errors

- export parity failure
- missing checkpoint

## Related Tools

`export_tflite`, `quantize_int8`, `benchmark_latency`

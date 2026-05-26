# quantize_report

Compare original and quantized checkpoints on the same evaluation set.

## Inputs

- `original_checkpoint`
- `quantized_checkpoint`
- `dataset_path`
- `split`
- `imgsz`
- `device`

## Outputs

- size deltas
- mAP50 deltas
- report duration

## Examples

```json
{"original_checkpoint":"run_demo","quantized_checkpoint":"~/exports/run_demo_int8.onnx","dataset_path":"~/data/mini_yolo"}
{"original_checkpoint":"~/models/retail.pt","quantized_checkpoint":"~/exports/retail_int8.onnx","dataset_path":"~/data/retail"}
{"original_checkpoint":"~/models/factory.pt","quantized_checkpoint":"~/exports/factory_int8.onnx","dataset_path":"~/data/factory","device":"cpu"}
```

## Common Errors

- missing original or quantized artifact
- evaluation failures from `eval_run`

## Related Tools

`quantize_int8`, `benchmark_latency`

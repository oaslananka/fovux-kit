# quantize_int8

Produce an INT8 ONNX export using a calibration dataset.

## Inputs

- `checkpoint`
- `calibration_dataset`
- `output_path`
- `imgsz`
- `device`

## Outputs

- quantized artifact path
- quantization duration
- size reduction percentage

## Examples

```json
{"checkpoint":"run_demo","calibration_dataset":"~/data/mini_yolo"}
{"checkpoint":"~/models/retail.pt","calibration_dataset":"~/data/retail","output_path":"~/exports/retail_int8.onnx"}
{"checkpoint":"~/models/factory.pt","calibration_dataset":"~/data/factory","device":"cpu"}
```

## Common Errors

- missing calibration dataset
- missing checkpoint

## Related Tools

`quantize_report`, `benchmark_latency`

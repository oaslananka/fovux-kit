# export_tflite

Export a checkpoint to TFLite, optionally with INT8 enabled.

## Inputs

- `checkpoint`
- `output_path`
- `imgsz`
- `half`
- `int8`
- `device`

## Outputs

- TFLite artifact path and export duration

## Examples

```json
{"checkpoint":"run_demo"}
{"checkpoint":"~/models/retail.pt","int8":true}
{"checkpoint":"~/models/factory.pt","output_path":"~/exports/factory.tflite"}
```

## Common Errors

- missing checkpoint
- upstream export failure from Ultralytics

## Related Tools

`export_onnx`, `quantize_int8`

# model_profile

Profile a checkpoint so you can choose between accuracy, size, and compute cost before training or export.

## Inputs

- `checkpoint`
- `imgsz`
- `device`

## Outputs

- parameter and gradient counts in millions
- GFLOPs when the backend can report them
- model layer count
- checkpoint size on disk
- rough inference memory estimate

## Examples

```json
{"checkpoint":"yolov8n.pt"}
{"checkpoint":"run_demo","imgsz":960}
```

## Common Errors

- missing checkpoint
- model backends that do not expose raw profiling metadata may report `gflops = 0.0`

## Related Tools

`benchmark_latency`, `export_onnx`, `train_start`

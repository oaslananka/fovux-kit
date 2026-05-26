# fovux_doctor

Inspect the local Fovux environment before training, exporting, or opening Studio live views.

## Inputs

This tool takes no arguments.

## Outputs

- Python runtime version
- GPU / accelerator availability
- import health for `ultralytics`, `onnxruntime`, `onnx`, and `fastmcp`
- `FOVUX_HOME` path, writability, free disk, and local inventory counts
- optional HTTP transport health summary
- warning and error lists suitable for CLI or Studio display

## Examples

```json
{}
```

## Common Errors

- generally does not fail hard; missing dependencies are reported in `warnings` or `errors`

## Related Tools

`model_profile`, `train_start`, `export_onnx`

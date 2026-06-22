# demo_init

Initialize a demo workspace for first-run onboarding.

## Inputs

- `target_path`: Path (absolute or relative to `FOVUX_HOME`) where the demo workspace directory structure will be created.

## Outputs

- `dataset_path`: Resolved path to the initialized sample YOLO dataset.
- `run_id`: The ID of the registered mock completed run.
- `run_path`: Resolved path to the mock run directory.
- `model_path`: Resolved path to the mock base model checkpoint (`yolov8n.pt`).
- `export_path`: Resolved path to the mock ONNX export model (`demo_model.onnx`).

## Examples

```json
{
  "target_path": "demo_workspace"
}
```

## Common Errors

- `PermissionError` if the destination path is not writable.

## Related Tools

`dataset_inspect`, `dataset_validate`, `model_list`, `run_compare`

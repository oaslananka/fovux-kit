# train_preflight

Perform preflight checks and return a diagnostic training compatibility summary.

## Inputs

- `dataset_path`
- `model`
- `epochs`, `batch`, `imgsz`, `device`
- `task`
- `name`, `tags`
- `options`, `max_runtime_seconds`, `max_disk_usage_gb`, `device_policy`

## Outputs

- `dataset_valid`
- `dataset_classes_count`
- `dataset_path`
- `model_valid`
- `model_source`
- `device_available`
- `resolved_device`
- `disk_space_valid`
- `available_disk_space_gb`
- `output_path_valid`
- `resolved_run_dir`
- `concurrency_valid`
- `active_runs_count`
- `warnings`

## Examples

```json
{"dataset_path":"~/data/mini_yolo"}
{"dataset_path":"~/data/retail","model":"yolov8s.pt","device_policy":"gpu_only"}
```

## Common Errors

- dataset path missing
- invalid YAML dataset configuration

## Related Tools

`train_start`, `train_status`, `train_stop`, `train_resume`

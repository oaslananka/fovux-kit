# train_start

Launch a non-blocking YOLO training subprocess.

## Inputs

- `dataset_path`
- `model`
- `epochs`, `batch`, `imgsz`, `device`
- `task`
- `name`, `tags`
- `extra_args`

## Outputs

- `run_id`
- `status`
- `pid`
- `run_path`

## Examples

```json
{"dataset_path":"~/data/mini_yolo","epochs":1}
{"dataset_path":"~/data/retail","model":"yolov8s.pt","epochs":50,"name":"retail_baseline"}
{"dataset_path":"~/data/factory","device":"cuda:0","extra_args":{"patience":20}}
```

## Common Errors

- dataset path missing
- requested run already running
- `force=true` with an existing run requires an available training slot and saves the old
  run to `FOVUX_HOME/archive/<run_id>.tar.gz` before replacing it. If an archive
  already exists, the replacement is refused instead of overwriting recovery data.

## Related Tools

`train_status`, `train_stop`, `train_resume`

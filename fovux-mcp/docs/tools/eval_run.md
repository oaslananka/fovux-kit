# eval_run

Run a validation pass on a checkpoint.

## Inputs

- `checkpoint`
- `dataset_path`
- `split`
- `batch`, `imgsz`, `device`
- `conf`, `iou`, `task`

## Outputs

- aggregate metrics such as mAP50, precision, and recall
- per-class stats
- evaluation duration

## Examples

```json
{"checkpoint":"~/runs/run_demo/weights/best.pt","dataset_path":"~/data/mini_yolo"}
{"checkpoint":"run_demo","dataset_path":"~/data/mini_yolo","split":"val"}
{"checkpoint":"~/models/baseline.pt","dataset_path":"~/data/retail","device":"cpu"}
```

## Common Errors

- checkpoint missing
- dataset missing

## Related Tools

`eval_per_class`, `eval_error_analysis`, `eval_compare`

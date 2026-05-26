# eval_error_analysis

Inspect confusion patterns and worst examples beyond headline metrics.

## Inputs

- `checkpoint`
- `dataset_path`
- `split`
- `top_n`
- `imgsz`, `device`, `conf`, `iou`

## Outputs

- confusion entries
- top error samples populated from saved validation predictions and ground-truth labels
- false-positive and false-negative counts
- evaluation duration

## Examples

```json
{"checkpoint":"run_demo","dataset_path":"~/data/mini_yolo"}
{"checkpoint":"~/models/retail.pt","dataset_path":"~/data/retail","top_n":20}
{"checkpoint":"~/models/factory.pt","dataset_path":"~/data/factory","conf":0.15}
```

## Common Errors

- missing dataset or checkpoint
- malformed or unsupported validation output from the underlying Ultralytics run

## Related Tools

`eval_run`, `eval_compare`, `run_compare`

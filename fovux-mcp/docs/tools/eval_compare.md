# eval_compare

Evaluate multiple checkpoints on the same dataset and rank the results.

## Inputs

- `checkpoints`
- `dataset_path`
- shared evaluation knobs: `split`, `batch`, `imgsz`, `device`, `conf`, `iou`

## Outputs

- ordered checkpoint comparison rows
- best checkpoint by mAP50 and mAP50-95

## Examples

```json
{"checkpoints":["run_a","run_b"],"dataset_path":"~/data/mini_yolo"}
{"checkpoints":["~/models/a.pt","~/models/b.pt"],"dataset_path":"~/data/retail"}
{"checkpoints":["run_small","run_large"],"dataset_path":"~/data/factory","device":"cpu"}
```

## Common Errors

- any checkpoint or dataset failure from `eval_run`

## Related Tools

`eval_run`, `run_compare`

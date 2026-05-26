# train_status

Read the latest state and metrics for a tracked training run.

## Inputs

- `run_id`

## Outputs

- status, pid, elapsed seconds
- current epoch and best mAP50 when `results.csv` is present
- run path

## Examples

```json
{"run_id":"run_demo"}
{"run_id":"retail_baseline"}
{"run_id":"factory_v2"}
```

## Common Errors

- `FOVUX_TRAIN_001` when the run is not in the registry

## Related Tools

`train_start`, `train_stop`, `run_compare`

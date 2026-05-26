# train_resume

Resume a stopped or failed run from its latest checkpoint.

## Inputs

- `run_id`
- optional `epochs`

## Outputs

- run id
- new subprocess pid
- resumed run path and status

## Examples

```json
{"run_id":"run_demo"}
{"run_id":"retail_baseline","epochs":80}
{"run_id":"factory_v2","epochs":120}
```

## Common Errors

- run not found
- missing `last.pt` in the run directory

## Related Tools

`train_start`, `train_stop`, `train_status`

# train_stop

Stop a running training subprocess and mark the run as stopped.

## Inputs

- `run_id`
- `force`

## Outputs

- resulting status
- user-facing stop message

## Examples

```json
{"run_id":"run_demo"}
{"run_id":"retail_baseline","force":true}
{"run_id":"factory_v2","force":false}
```

## Common Errors

- run missing from registry

## Related Tools

`train_status`, `train_resume`

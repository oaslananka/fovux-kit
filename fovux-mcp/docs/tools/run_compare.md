# run_compare

Generate a markdown and PNG summary across multiple training runs.

## Inputs

- `run_ids`
- `output_path`

## Outputs

- compared run summaries
- best run id
- generated markdown report path
- generated chart path

## Examples

```json
{"run_ids":["run_a","run_b"]}
{"run_ids":["retail_v1","retail_v2"],"output_path":"~/exports/retail_compare"}
{"run_ids":[]}
```

## Common Errors

- unknown run id

## Related Tools

`train_status`, `eval_compare`, `model_list`

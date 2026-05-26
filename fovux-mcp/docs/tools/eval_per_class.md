# eval_per_class

Return a sorted per-class view over evaluation output.

## Inputs

- `checkpoint`
- `dataset_path`
- evaluation knobs from `eval_run`
- `sort_by`
- `ascending`

## Outputs

- ordered per-class metric rows plus the aggregate eval context

## Examples

```json
{"checkpoint":"run_demo","dataset_path":"~/data/mini_yolo"}
{"checkpoint":"~/models/retail.pt","dataset_path":"~/data/retail","sort_by":"precision"}
{"checkpoint":"~/models/factory.pt","dataset_path":"~/data/factory","ascending":false}
```

## Common Errors

- same failure modes as `eval_run`

## Related Tools

`eval_run`, `eval_error_analysis`

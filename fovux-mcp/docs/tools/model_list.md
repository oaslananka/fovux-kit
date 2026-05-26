# model_list

List tracked checkpoints and exported model artifacts.

## Inputs

- `offset` — optional pagination offset, defaults to `0`
- `limit` — optional page size, defaults to `50`

## Outputs

- discovered models under `~/.fovux/models`
- run-local weights and exports under `~/.fovux/runs`
- task, run id, size, source, and timestamps when available
- `offset`, `limit`, and `total` so Studio can page large model inventories

## Examples

```json
{}
{"offset":0,"limit":25}
{"offset":25,"limit":25}
```

## Common Errors

- usually returns an empty list instead of failing when nothing is tracked

## Related Tools

`run_compare`, `export_onnx`, `export_tflite`

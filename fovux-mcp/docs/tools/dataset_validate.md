# dataset_validate

Deep integrity checks for YOLO datasets.

## Inputs

- `dataset_path`
- `format`
- `check_image_readable`
- `check_bbox_bounds`
- `check_class_id_range`
- `strict`

## Outputs

- `valid`
- structured `errors` and `warnings`
- one-line `summary`
- optional `remediation_script`

## Examples

```json
{"dataset_path":"~/data/mini_yolo"}
{"dataset_path":"~/data/warehouse","strict":true}
{"dataset_path":"~/data/retail","check_image_readable":false}
```

## Common Errors

- unsupported non-YOLO format
- missing dataset path

## Related Tools

`dataset_inspect`, `dataset_convert`

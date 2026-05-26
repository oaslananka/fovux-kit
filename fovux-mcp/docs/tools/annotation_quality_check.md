# annotation_quality_check

Inspect YOLO labels for common annotation mistakes before a bad dataset wastes training time.

## Inputs

- `dataset_path`
- optional `checks` list

## Outputs

- total image count
- aggregate issue counts by rule
- representative issue rows with file paths and messages

## Checks

- invalid class ids
- empty label files
- tiny bounding boxes
- out-of-bounds YOLO coordinates
- near-identical overlapping boxes
- extremely crowded images

## Examples

```json
{ "dataset_path": "~/data/warehouse" }
```

## Common Errors

- dataset path missing
- non-YOLO datasets should be converted before running this tool

## Related Tools

`dataset_inspect`, `dataset_validate`, `eval_error_analysis`

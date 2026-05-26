# dataset_split

Create reproducible train, val, and test splits.

## Inputs

- `dataset_path`
- `train_ratio`, `val_ratio`, `test_ratio`
- `stratify_by_class`
- `seed`
- `output_format`
- `overwrite`
- `output_path`

## Outputs

- split counts
- stratification report
- output directory and manifest path

## Examples

```json
{"dataset_path":"~/data/mini_yolo","output_path":"~/data/mini_yolo_split"}
{"dataset_path":"~/data/retail","train_ratio":0.8,"val_ratio":0.1,"test_ratio":0.1}
{"dataset_path":"~/data/warehouse","seed":7,"overwrite":true}
```

## Common Errors

- non-YOLO input
- empty dataset

## Related Tools

`dataset_inspect`, `dataset_convert`

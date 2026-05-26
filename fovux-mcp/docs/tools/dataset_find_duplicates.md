# dataset_find_duplicates

Perceptual hash duplicate detection for image datasets.

## Inputs

- `dataset_path`
- `algorithm`: `phash`, `dhash`, `whash`, `avg`
- `hamming_threshold`
- `across_splits`

## Outputs

- duplicate groups
- total duplicate count and percentage
- total image count and analysis duration

## Examples

```json
{"dataset_path":"~/data/mini_yolo"}
{"dataset_path":"~/data/retail","algorithm":"dhash","hamming_threshold":3}
{"dataset_path":"~/data/factory","across_splits":false}
```

## Common Errors

- dataset not found
- empty dataset

## Related Tools

`dataset_inspect`, `dataset_validate`

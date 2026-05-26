# dataset_inspect

Comprehensive dataset statistics for YOLO or COCO exports.

## Inputs

- `dataset_path`: dataset root
- `format`: `auto`, `yolo`, `coco`, or `voc`
- `include_samples`: include sample image paths
- `max_images_analyzed`: sampling cap for very large datasets

## Outputs

- detected format, image/annotation counts, class stats, orphan counts
- split detection, distribution histograms, warnings, and sample paths

## Examples

```json
{"dataset_path":"~/data/mini_yolo"}
{"dataset_path":"~/data/retail","format":"yolo","include_samples":false}
{"dataset_path":"~/exports/coco128","format":"coco","max_images_analyzed":5000}
```

## Common Errors

- `FOVUX_DATASET_001`: missing dataset path
- `FOVUX_DATASET_002`: unsupported or malformed dataset format
- `FOVUX_DATASET_003`: zero images discovered

## Related Tools

`dataset_validate`, `dataset_find_duplicates`, `dataset_split`

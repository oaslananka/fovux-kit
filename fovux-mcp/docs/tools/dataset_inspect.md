# dataset_inspect

Comprehensive dataset statistics and quality intelligence for YOLO or COCO exports.

YOLO and COCO adapters populate the same internal `DatasetInventory`; shared analysis then computes
class balance, annotation counts, bounding-box anomalies, perceptual duplicates, split leakage, quality
score, and auto-fix guidance once. Public output fields remain backward compatible.

## Inputs

- `dataset_path`: dataset root
- `format`: `auto`, `yolo`, `coco`, or `voc` (`voc` detection is accepted but inspection remains unsupported)
- `include_samples`: include sample image paths
- `max_images_analyzed`: cap expensive image decoding and fingerprinting for large datasets

The complete inventory still reports all declared/discovered images and annotations. The analysis cap
limits only image decoding, dimensions, perceptual hashes, and sample-path evidence.

## Outputs

- detected format, image/annotation counts, normalized class statistics, and orphan counts
- split detection, image/bounding-box/count histograms, warnings, and sample paths
- `quality_score`, `class_balance_gini`, `label_anomalies`, duplicate groups, and leakage findings
- human-readable `dataset_card` and non-destructive `auto_fix_plan`

COCO pixel boxes are normalized to image-relative coordinates for shared anomaly checks while raw pixel
areas remain available for the existing COCO histogram semantics.

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

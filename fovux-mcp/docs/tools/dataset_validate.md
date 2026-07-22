# dataset_validate

Deep integrity checks for YOLO and COCO datasets.

Both formats are translated into the shared internal `DatasetInventory` model before validation. This
keeps readable-image, bounding-box, class, orphan, and metadata findings aligned across formats without
changing the public tool schema.

## Inputs

- `dataset_path`
- `format`: `auto`, `yolo`, or `coco` (`voc` remains unsupported)
- `check_image_readable`
- `check_bbox_bounds`
- `check_class_id_range`
- `strict`

## Outputs

- `valid`
- structured `errors` and `warnings`
- one-line `summary`
- optional `remediation_script`

Bounding boxes are checked in normalized image-relative coordinates. YOLO class IDs are checked against
`nc`; COCO category IDs are checked against the declared category registry. Missing or corrupt COCO image
files are reported with the same `Image unreadable` semantics used for YOLO.

Remediation remains explain-first. The optional clipping script is emitted only for YOLO text label files;
COCO JSON findings are reported without generating an unsafe format-specific rewrite.

## Examples

```json
{"dataset_path":"~/data/mini_yolo"}
{"dataset_path":"~/exports/coco128","format":"coco"}
{"dataset_path":"~/data/warehouse","strict":true}
{"dataset_path":"~/data/retail","check_image_readable":false}
```

## Common Errors

- unsupported format other than YOLO or COCO
- missing dataset path
- malformed format metadata

## Related Tools

`dataset_inspect`, `dataset_convert`

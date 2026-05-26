# dataset_convert

Convert between supported YOLO and COCO dataset layouts.

## Inputs

- `source_path`
- `source_format`
- `target_format`
- `target_path`
- `copy_images`
- optional `class_map`

## Outputs

- images processed
- converted and skipped annotation counts
- skip reasons and output path

## Examples

```json
{"source_path":"~/data/mini_yolo","target_path":"~/data/mini_coco","target_format":"coco"}
{"source_path":"~/data/coco_export","target_path":"~/data/yolo_export","target_format":"yolo","source_format":"coco"}
{"source_path":"~/data/retail","target_path":"~/data/retail_coco","target_format":"coco","copy_images":true}
```

## Common Errors

- unsupported direction such as VOC paths in v1.0.0
- source equals target format

## Related Tools

`dataset_inspect`, `dataset_validate`

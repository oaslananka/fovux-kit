# dataset_augment

Create a local augmented YOLO dataset copy using deterministic transforms.

## Overview

`dataset_augment` applies image augmentation techniques to an existing YOLO dataset and writes the augmented images and labels to a new output directory. The original dataset is never modified.

## Input Schema

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `dataset_path` | `string` | Yes | — | Path to the source YOLO dataset directory. |
| `techniques` | `list[string]` | No | `["flip_h"]` | Augmentation techniques to apply: `flip_h`, `flip_v`, `cutout`. |
| `multiplier` | `integer` | No | `3` | Number of augmented copies per source image. |
| `output_path` | `string` | Yes | — | Path to write the augmented dataset. |

## Output Schema

| Field | Type | Description |
|---|---|---|
| `dataset_path` | `string` | Resolved source dataset path. |
| `output_path` | `string` | Resolved output dataset path. |
| `source_images` | `integer` | Number of source images found. |
| `generated_images` | `integer` | Total augmented images created. |
| `techniques` | `list[string]` | Techniques applied. |
| `manifest_path` | `string` | Path to the augmentation manifest JSON. |

## Examples

### CLI
```bash
fovux-mcp serve --http
curl -X POST http://127.0.0.1:7823/tools/dataset_augment \
  -H "Authorization: Bearer $(cat ~/.fovux/auth.token)" \
  -H "Content-Type: application/json" \
  -d '{"dataset_path": "/data/yolo_set", "output_path": "/data/yolo_aug", "techniques": ["flip_h", "flip_v"], "multiplier": 2}'
```

### Python
```python
from fovux.tools.dataset_augment import dataset_augment
result = dataset_augment("/data/yolo_set", techniques=["flip_h"], multiplier=3, output_path="/data/yolo_aug")
```

## Notes & Limits

- The `data.yaml` file is copied from the source to the output directory.
- Labels are adjusted to match the applied augmentation (e.g., bounding box x-coordinates are mirrored for `flip_h`).
- `cutout` places a black rectangle over the center 30% of the image.
- Large datasets with high multipliers may consume significant disk space.

## Failure Modes

- `FovuxDatasetNotFoundError` if the source dataset path does not exist.
- `ValueError` if `output_path` is not specified.
- Validation error if `data.yaml` is missing or malformed.

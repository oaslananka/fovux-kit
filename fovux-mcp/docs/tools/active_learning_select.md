# active_learning_select

Rank unlabeled images by model uncertainty for annotation prioritization.

## Overview

`active_learning_select` runs inference on an unlabeled image pool using a trained checkpoint and ranks images by an uncertainty strategy. Returns the top-N most informative images for human annotation.

## Input Schema

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `checkpoint` | `string` | Yes | — | Model checkpoint name or path. |
| `unlabeled_pool` | `string` | Yes | — | Path to the directory of unlabeled images. |
| `strategy` | `string` | No | `"entropy"` | Scoring strategy: `entropy`, `least_confident`, `margin`. |
| `budget` | `integer` | No | `100` | Maximum number of images to select. |
| `imgsz` | `integer` | No | `640` | Inference input image size. |
| `conf` | `float` | No | `0.25` | Minimum confidence threshold. |
| `device` | `string` | No | `"auto"` | Inference device. |

## Output Schema

| Field | Type | Description |
|---|---|---|
| `checkpoint` | `string` | Checkpoint used for scoring. |
| `strategy` | `string` | Uncertainty strategy applied. |
| `budget` | `integer` | Requested budget. |
| `selected` | `list[object]` | Ranked list of `{image_path, score, strategy}` entries. |

## Examples

### CLI
```bash
curl -X POST http://127.0.0.1:7823/tools/active_learning_select \
  -H "Authorization: Bearer $(cat ~/.fovux/auth.token)" \
  -H "Content-Type: application/json" \
  -d '{"checkpoint": "yolov8n.pt", "unlabeled_pool": "/data/unlabeled", "strategy": "entropy", "budget": 50}'
```

### Python
```python
from fovux.tools.active_learning_select import active_learning_select
result = active_learning_select("yolov8n.pt", "/data/unlabeled", strategy="entropy", budget=50)
```

## Notes & Limits

- Each image in the pool is processed individually; large pools may be slow.
- Images without detections receive the maximum uncertainty score (1.0).
- The `margin` strategy requires at least two detections per image to be meaningful.

## Failure Modes

- `FovuxDatasetNotFoundError` if the unlabeled pool path does not exist.
- Model loading errors if the checkpoint is not found or corrupt.

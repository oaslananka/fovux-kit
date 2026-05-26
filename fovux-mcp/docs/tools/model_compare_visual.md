# model_compare_visual

Generate visual comparison artifacts between two model checkpoints.

## Overview

`model_compare_visual` runs both models on a set of test images and produces side-by-side detection overlays for visual inspection of prediction differences.

## Input Schema

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `checkpoint_a` | `string` | Yes | — | First model checkpoint. |
| `checkpoint_b` | `string` | Yes | — | Second model checkpoint. |
| `image_paths` | `list[string]` | Yes | — | Paths to test images. |
| `output_dir` | `string` | Yes | — | Directory for comparison outputs. |
| `imgsz` | `integer` | No | `640` | Inference image size. |
| `conf` | `float` | No | `0.25` | Confidence threshold. |
| `device` | `string` | No | `"auto"` | Inference device. |

## Output Schema

| Field | Type | Description |
|---|---|---|
| `checkpoint_a` | `string` | First checkpoint path. |
| `checkpoint_b` | `string` | Second checkpoint path. |
| `comparison_images` | `list[string]` | Paths to generated comparison images. |
| `image_count` | `integer` | Number of comparisons generated. |

## Examples

### CLI
```bash
curl -X POST http://127.0.0.1:7823/tools/model_compare_visual \
  -H "Authorization: Bearer $(cat ~/.fovux/auth.token)" \
  -H "Content-Type: application/json" \
  -d '{"checkpoint_a": "yolov8n.pt", "checkpoint_b": "yolov8s.pt", "image_paths": ["/data/img1.jpg"], "output_dir": "/tmp/compare"}'
```

### Python
```python
from fovux.tools.model_compare_visual import model_compare_visual
result = model_compare_visual("yolov8n.pt", "yolov8s.pt", ["/data/img1.jpg"], output_dir="/tmp/compare")
```

## Notes & Limits

- Output images are saved as PNG with side-by-side detection overlays.
- Large image sets may produce many output files.

## Failure Modes

- Checkpoint resolution errors if either model is not found.
- File not found for any image path that does not exist.

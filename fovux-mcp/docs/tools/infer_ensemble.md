# infer_ensemble

Run inference with multiple checkpoints and fuse the detections.

## Overview

`infer_ensemble` runs inference on a single image using multiple YOLO checkpoints, then fuses the detections using class-aware NMS-style deduplication. Returns the combined detection set.

## Input Schema

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `checkpoints` | `list[string]` | Yes | — | List of checkpoint paths or names. |
| `image_path` | `string` | Yes | — | Path to the input image. |
| `fusion_method` | `string` | No | `"wbf"` | Detection fusion method: `wbf` (weighted box fusion). |
| `weights` | `list[float]` | No | `null` | Per-checkpoint weights for fusion. |
| `imgsz` | `integer` | No | `640` | Inference image size. |
| `conf` | `float` | No | `0.25` | Confidence threshold. |
| `device` | `string` | No | `"auto"` | Inference device. |

## Output Schema

| Field | Type | Description |
|---|---|---|
| `checkpoints` | `list[string]` | Checkpoints used. |
| `image_path` | `string` | Input image path. |
| `fusion_method` | `string` | Fusion method applied. |
| `detections` | `list[object]` | Fused detection list. |
| `detection_count` | `integer` | Number of fused detections. |

## Examples

### CLI
```bash
curl -X POST http://127.0.0.1:7823/tools/infer_ensemble \
  -H "Authorization: Bearer $(cat ~/.fovux/auth.token)" \
  -H "Content-Type: application/json" \
  -d '{"checkpoints": ["yolov8n.pt", "yolov8s.pt"], "image_path": "/data/test.jpg"}'
```

### Python
```python
from fovux.tools.infer_ensemble import infer_ensemble
result = infer_ensemble(["yolov8n.pt", "yolov8s.pt"], "/data/test.jpg", fusion_method="wbf")
```

## Notes & Limits

- Detections are deduplicated using IoU > 0.5 for same-class boxes.
- Higher-confidence detections are kept when overlapping boxes are found.
- Processing time scales linearly with the number of checkpoints.

## Failure Modes

- Checkpoint resolution errors for any invalid checkpoint.
- File not found if the image path does not exist.

# distill_model

Start a student-model training run with teacher-model distillation metadata.

## Overview

`distill_model` launches a YOLO training run for a student model, recording the teacher checkpoint, temperature, and alpha parameters as distillation metadata. The underlying training uses the standard `train_start` pipeline.

## Input Schema

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `teacher_checkpoint` | `string` | Yes | — | Path or name of the teacher model checkpoint. |
| `dataset_path` | `string` | Yes | — | Path to the YOLO training dataset. |
| `student_model` | `string` | No | `"yolov8n.pt"` | Student model architecture. |
| `temperature` | `float` | No | `4.0` | Distillation temperature. |
| `alpha` | `float` | No | `0.7` | Distillation loss weight (0–1). |
| `epochs` | `integer` | No | `100` | Number of training epochs. |
| `batch` | `integer` | No | `16` | Batch size. |
| `imgsz` | `integer` | No | `640` | Training image size. |
| `device` | `string` | No | `"auto"` | Training device. |
| `name` | `string` | No | `null` | Optional run name. |

## Output Schema

| Field | Type | Description |
|---|---|---|
| `run_id` | `string` | ID of the created training run. |
| `status` | `string` | Run status (`running`, `pending`). |
| `pid` | `integer` | Process ID of the training worker. |
| `run_path` | `string` | Local path to the run directory. |
| `teacher_checkpoint` | `string` | Resolved teacher checkpoint path. |
| `student_model` | `string` | Student model used. |

## Examples

### CLI
```bash
curl -X POST http://127.0.0.1:7823/tools/distill_model \
  -H "Authorization: Bearer $(cat ~/.fovux/auth.token)" \
  -H "Content-Type: application/json" \
  -d '{"teacher_checkpoint": "yolov8l.pt", "dataset_path": "/data/yolo_set", "student_model": "yolov8n.pt"}'
```

### Python
```python
from fovux.tools.distill_model import distill_model
result = distill_model("yolov8l.pt", "/data/yolo_set", student_model="yolov8n.pt", temperature=4.0)
```

## Notes & Limits

- Distillation metadata is recorded in the run's `params.json` as `extra_args`.
- The actual distillation loss computation depends on the Ultralytics model supporting teacher-student flows.
- The run is tagged with `["distillation"]` automatically.

## Failure Modes

- Checkpoint resolution errors if the teacher model is not found.
- Standard `train_start` errors for dataset validation and concurrent run limits.

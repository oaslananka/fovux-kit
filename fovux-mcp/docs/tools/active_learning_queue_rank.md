# active_learning_queue_rank

Rank unlabeled images by uncertainty using a YOLO checkpoint and populate the review queue.

## Inputs

- `checkpoint`: Path to the YOLO model checkpoint weights.
- `unlabeled_pool`: Path to the folder containing unlabeled images.
- `dataset_path`: Path to the destination YOLO dataset directory.
- `strategy`: Strategy for scoring uncertainty (`entropy`, `margin`, `least_confident`).
- `limit`: Maximum number of images to rank.
- `imgsz`: Inference image size.
- `conf`: Confidence threshold.
- `device`: Device to run inference on.

## Outputs

- `ranked_count`: Number of images processed and added.
- `queue_entries`: List of review queue entries.

## Examples

```json
{
  "checkpoint": "yolov8n.pt",
  "unlabeled_pool": "pool",
  "dataset_path": "dataset"
}
```

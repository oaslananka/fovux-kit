# active_learning_queue_submit

Submit label corrections for a queue entry, copy the image to the dataset, and write the YOLO label file.

## Inputs

- `entry_id`: Unique review queue entry identifier.
- `corrected_labels`: List of corrected detections with bounding boxes.
- `dataset_split`: Split directory name (`train` or `val`).

## Outputs

- `entry_id`: The submitted entry identifier.
- `status`: Status, which is updated to `reviewed`.
- `copied_image_path`: Path to the copied image in the target dataset split.
- `written_label_path`: Path to the generated YOLO label file.

## Examples

```json
{
  "entry_id": "abc123hash",
  "corrected_labels": [
    {
      "class_id": 0,
      "class_name": "cat",
      "confidence": 1.0,
      "bbox_xyxy": [0.1, 0.1, 0.2, 0.2]
    }
  ]
}
```

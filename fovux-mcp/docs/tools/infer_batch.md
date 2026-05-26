# infer_batch

Run inference over an image directory and persist the detections as a reusable manifest.

## Inputs

- `checkpoint`
- `input_dir`
- `output_dir`
- `imgsz`, `conf`, `device`, `batch_size`
- `save_annotated`
- `export_format` — `json`, `csv`, or `yolo_labels`

## Outputs

- number of processed images
- total detection count
- manifest path for the chosen export format
- optional annotated image directory
- a small preview list for Studio or CLI summaries

## Examples

```json
{"checkpoint":"yolov8n.pt","input_dir":"~/images"}
{"checkpoint":"run_demo","input_dir":"~/images","export_format":"csv","save_annotated":false}
```

## Common Errors

- input directory missing
- no supported images found under the input directory

## Related Tools

`infer_image`, `benchmark_latency`, `model_profile`

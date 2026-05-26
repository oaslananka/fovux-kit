# infer_image

Run structured inference on a single image.

## Inputs

- `checkpoint`
- `image_path`
- `imgsz`, `conf`, `iou`, `device`
- `save_image`
- `output_path`

## Outputs

- detections
- counts by class
- optional rendered image path

## Examples

```json
{"checkpoint":"run_demo","image_path":"~/samples/frame.jpg"}
{"checkpoint":"~/models/retail.pt","image_path":"~/samples/shelf.png","save_image":true}
{"checkpoint":"~/models/factory.pt","image_path":"~/samples/cam01.jpg","conf":0.15}
```

## Common Errors

- missing checkpoint
- unreadable image

## Related Tools

`infer_rtsp`, `benchmark_latency`

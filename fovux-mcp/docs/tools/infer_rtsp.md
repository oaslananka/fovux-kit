# infer_rtsp

Run live inference over an RTSP stream with reconnection logic.

## Inputs

- `checkpoint`
- `rtsp_url`
- `duration_seconds`
- `imgsz`, `conf`, `frame_skip`, `device`
- `save_video`
- `output_path`

## Outputs

- processed, skipped, and dropped frame counts
- average FPS
- detection totals and optional video path

## Examples

```json
{"checkpoint":"run_demo","rtsp_url":"rtsp://camera.local/stream"}
{"checkpoint":"~/models/retail.pt","rtsp_url":"rtsp://example/retail","duration_seconds":10}
{"checkpoint":"~/models/factory.pt","rtsp_url":"rtsp://example/factory","frame_skip":2,"save_video":true}
```

## Common Errors

- `FOVUX_INFER_001` when the stream cannot be opened

## Related Tools

`infer_image`, `benchmark_latency`

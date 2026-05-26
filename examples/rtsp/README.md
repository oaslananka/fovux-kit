# RTSP Mock Example

This example is a placeholder for the weekly slow pipeline path. It keeps the
product contract explicit without requiring a public camera stream.

```bash
docker compose up --build
fovux-mcp infer_rtsp \
  --checkpoint ~/.fovux/runs/demo/weights/best.pt \
  --rtsp-url rtsp://127.0.0.1:8554/demo \
  --duration-seconds 30 \
  --save-video
```

The v2 RTSP implementation uses reconnect backoff, a bounded capture queue, and
dynamic output FPS so a broken stream does not spin the CPU.

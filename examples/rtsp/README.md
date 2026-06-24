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

## MediaMTX Image Pin

The mock RTSP server uses `bluenviron/mediamtx:1.19.0` pinned to the
multi-platform image index digest
`sha256:35f9e8aefaca5352b5f4667c8cd529360a53a493c51fa639e8f5898c03bc0d06`.

To refresh the pin, verify the latest upstream release and Docker tag:

```bash
gh api repos/bluenviron/mediamtx/releases/latest --jq '.tag_name, .published_at'
MEDIAMTX_VERSION=1.19.0
docker buildx imagetools inspect "docker.io/bluenviron/mediamtx:${MEDIAMTX_VERSION}"
docker compose -f examples/rtsp/docker-compose.yml config
docker compose -f examples/rtsp/docker-compose.yml pull
```

Use the numeric Docker tag without the `v` prefix, then copy the image index
digest into `examples/rtsp/docker-compose.yml`.

The v2 RTSP implementation uses reconnect backoff, a bounded capture queue, and
dynamic output FPS so a broken stream does not spin the CPU.

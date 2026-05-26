# Fovux Quickstart Example

This folder documents the release smoke path used for demos:

1. Prepare a tiny YOLO dataset with `data.yaml`, `images/train`, `images/val`, `labels/train`, and `labels/val`.
2. Start the local HTTP server with authentication:

```bash
fovux-mcp serve --http --tcp --metrics
```

3. Launch training from Fovux Studio or call the tool directly:

```bash
curl -H "Authorization: Bearer $(cat ~/.fovux/auth.token)" \
  -H "content-type: application/json" \
  -d '{"dataset_path":"./dataset","model":"yolov8n.pt","epochs":3,"imgsz":64,"device":"cpu"}' \
  http://127.0.0.1:7823/tools/train_start
```

4. Watch live metrics in the dashboard, export ONNX, and run `benchmark_latency`.

The checked-in repository intentionally keeps binary fixtures small. Use
`fovux-mcp/tests/fixtures/mini_yolo` as the canonical tiny dataset when running
this flow locally.

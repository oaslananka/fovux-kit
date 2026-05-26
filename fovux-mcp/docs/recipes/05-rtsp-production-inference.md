# Recipe 05 — RTSP Production Inference

1. Validate the chosen checkpoint on held-out data with `eval_run`.
2. Export and benchmark if you plan to serve through ONNX or TFLite.
3. Run `infer_rtsp` against the real stream source.
4. Observe dropped frames, FPS, and detection counts before making deployment decisions.

This recipe is especially useful for factory cameras, warehouse feeds, and other always-on edge environments.

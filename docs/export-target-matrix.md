# Export Target Matrix

This matrix tracks the current Fovux export posture for YOLO exports. It separates implemented one-click tools from planned/manual formats so agents do not claim unsupported conversions.

Source reference: <https://docs.ultralytics.com/modes/export/>

| Family | Format arg | Typical artifact | Fovux status | Notes |
| --- | --- | --- | --- | --- |
| PyTorch | `-` | `.pt` | Source checkpoint | Training output and source for exports. |
| ONNX | `onnx` | `.onnx` | Implemented: `export_onnx` | Primary portable format for CPU, GPU, browser/WASM, and TensorRT input. |
| TensorRT | `engine` | `.engine` | Planned/manual | Use ONNX as intermediate until engine tool exists. |
| CoreML | `coreml` | `.mlpackage` | Planned/manual | Apple deployment target; requires macOS validation. |
| OpenVINO | `openvino` | `_openvino_model/` | Planned/manual | Intel/CPU target; requires parity and benchmark evidence. |
| TFLite | `tflite` | `.tflite` | Implemented: `export_tflite`, `quantize_int8` | Android and Raspberry Pi class targets. |
| NCNN | `ncnn` | `_ncnn_model/` | Planned/manual | Lightweight edge/mobile target. |
| RKNN | `rknn` | `_rknn_model/` | Planned/manual | Rockchip target; requires device-specific validation. |

Required export arguments to track: `imgsz`, `batch`, `device`, `dynamic`, `half`, `int8`, `data`, `fraction`, `opset`, `simplify`, and TensorRT `workspace`.

Agents must use `export_onnx`, `export_tflite`, or `quantize_int8` for implemented flows. Other formats remain planned/manual until Fovux has a tool, tests, parity check, and benchmark gate.

# Deployment Advice Profiles

`deployment_advise` provides target-aware guidance for edge and local deployment planning.

## Required target profiles

| Profile | Recommended export | Runtime | Quantization | Validation command | Benchmark command | Caveats |
| --- | --- | --- | --- | --- | --- | --- |
| Jetson / TensorRT | ONNX then TensorRT engine | TensorRT | FP16 or INT8 with calibration | `deployment_advise --target-profile jetson` | `benchmark_latency --backend tensorrt` | CUDA/TensorRT version and memory bound. |
| Raspberry Pi | TFLite or ONNX Runtime CPU | TFLite/ONNX Runtime | INT8 when calibrated | `deployment_advise --target-profile raspberry_pi` | `benchmark_latency --backend tflite` | ARM CPU latency and RAM bound. |
| Apple Silicon | CoreML or ONNX | CoreML / MPS | FP16 where supported | planned/manual CoreML validation | benchmark on target Mac | Requires macOS target validation. |
| OpenVINO CPU/iGPU | OpenVINO IR or ONNX | OpenVINO | INT8 with calibration | planned/manual OpenVINO validation | benchmark on Intel target | Requires OpenVINO runtime and parity evidence. |
| TFLite / Edge TPU | TFLite / Edge TPU TFLite | TFLite / Edge TPU | INT8 required for Edge TPU | TFLite parity check | TFLite benchmark | Operator support can block compilation. |
| NCNN / mobile | NCNN | NCNN | FP16 or INT8 by device | planned/manual NCNN validation | device benchmark | Mobile kernels vary by SoC. |
| Browser / ONNX Runtime Web | ONNX | ONNX Runtime Web | FP16 where supported | browser sample inference | WASM/WebGPU benchmark | Browser memory and postprocessing constraints. |
| Generic CPU / industrial edge | ONNX | ONNX Runtime CPU / OpenVINO | FP32 or INT8 | ONNX parity check | ONNX Runtime benchmark | Prefer stable deterministic CPU path. |

Advice must include export format, quantization approach, validation command, benchmark command, and caveats.

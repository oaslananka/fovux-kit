export type ExportTargetDevice =
  | "desktop_cpu"
  | "desktop_gpu"
  | "desktop_tensorrt"
  | "raspberry_pi_5"
  | "jetson_nano"
  | "mobile_android";

export interface ExportTargetProfile {
  id: ExportTargetDevice;
  label: string;
  description: string;
  format: "onnx" | "tflite";
  quantize: boolean;
  verifyParity: boolean;
  group: "cpu" | "gpu" | "edge" | "mobile";
  requiresCuda?: boolean;
  benchmarkBackend?: "onnxruntime" | "tflite" | "tensorrt";
}

export interface BenchmarkSummary {
  latency_p50_ms?: number;
  latency_p95_ms?: number;
  model_size_mb?: number;
}

export interface ExportRecommendation {
  targetId: ExportTargetDevice;
  label: string;
  message: string;
}

export const EXPORT_TARGETS: ExportTargetProfile[] = [
  {
    id: "desktop_cpu",
    label: "Desktop CPU",
    description: "Balanced default for x86 inference on ONNX Runtime CPU.",
    format: "onnx",
    quantize: false,
    verifyParity: true,
    group: "cpu",
    benchmarkBackend: "onnxruntime",
  },
  {
    id: "desktop_gpu",
    label: "Desktop GPU",
    description: "Keep full-fidelity ONNX for accelerated local serving.",
    format: "onnx",
    quantize: false,
    verifyParity: true,
    group: "gpu",
    benchmarkBackend: "onnxruntime",
  },
  {
    id: "desktop_tensorrt",
    label: "TensorRT Engine",
    description:
      "GPU target for CUDA hosts; starts from ONNX and validates TensorRT runtime availability.",
    format: "onnx",
    quantize: false,
    verifyParity: false,
    group: "gpu",
    requiresCuda: true,
    benchmarkBackend: "tensorrt",
  },
  {
    id: "raspberry_pi_5",
    label: "Raspberry Pi 5",
    description: "Prefer a compact TFLite export with INT8 quantization.",
    format: "tflite",
    quantize: true,
    verifyParity: false,
    group: "edge",
    benchmarkBackend: "tflite",
  },
  {
    id: "jetson_nano",
    label: "Jetson Nano",
    description:
      "Prepare an ONNX artifact that can feed a later TensorRT step.",
    format: "onnx",
    quantize: true,
    verifyParity: false,
    group: "gpu",
    requiresCuda: true,
    benchmarkBackend: "tensorrt",
  },
  {
    id: "mobile_android",
    label: "Mobile Android",
    description: "Optimized for lightweight TFLite deployment on-device.",
    format: "tflite",
    quantize: true,
    verifyParity: false,
    group: "mobile",
    benchmarkBackend: "tflite",
  },
];

export function suggestExportPath(
  checkpointPath: string,
  fovuxHome: string,
  format: "onnx" | "tflite",
  quantize: boolean,
): string {
  const checkpointName = checkpointPath.split(/[\\/]/).pop() ?? "model.pt";
  const stem = checkpointName.replace(/\.[^.]+$/, "");
  const suffix = format === "onnx" ? ".onnx" : ".tflite";
  const filename = quantize ? `${stem}-int8${suffix}` : `${stem}${suffix}`;
  const separator =
    fovuxHome.endsWith("\\") || fovuxHome.endsWith("/") ? "" : "\\";
  return `${fovuxHome}${separator}exports\\${filename}`;
}

export function recommendExportTarget(
  summary: BenchmarkSummary,
): ExportRecommendation {
  const p95 =
    summary.latency_p95_ms ??
    summary.latency_p50_ms ??
    Number.POSITIVE_INFINITY;
  const sizeMb = summary.model_size_mb ?? 0;
  if (p95 <= 35 && sizeMb <= 80) {
    return {
      targetId: "raspberry_pi_5",
      label: "Raspberry Pi 5 ready",
      message:
        "Latency and size look suitable for compact ARM edge deployment.",
    };
  }
  if (p95 <= 90 && sizeMb <= 220) {
    return {
      targetId: "jetson_nano",
      label: "Jetson Nano recommended",
      message: "This model is better matched to a CUDA-capable edge device.",
    };
  }
  if (p95 <= 140) {
    return {
      targetId: "desktop_cpu",
      label: "Desktop CPU recommended",
      message:
        "Usable locally, but likely too heavy for small single-board devices.",
    };
  }
  return {
    targetId: "desktop_gpu",
    label: "GPU target recommended",
    message:
      "Latency is high enough that GPU acceleration or a smaller model is advisable.",
  };
}

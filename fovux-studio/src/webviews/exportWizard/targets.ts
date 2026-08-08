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
    description: "Prepare an ONNX artifact that can feed a later TensorRT step.",
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
  quantize: boolean
): string {
  const checkpointName = checkpointPath.split(/[\\/]/).pop() ?? "model.pt";
  const stem = checkpointName.replace(/\.[^.]+$/, "");
  const suffix = format === "onnx" ? ".onnx" : ".tflite";
  const filename = quantize ? `${stem}-int8${suffix}` : `${stem}${suffix}`;
  const separator = fovuxHome.endsWith("\\") || fovuxHome.endsWith("/") ? "" : "\\";
  return `${fovuxHome}${separator}exports\\${filename}`;
}

export function recommendExportTarget(summary: BenchmarkSummary): ExportRecommendation {
  const p95 = summary.latency_p95_ms ?? summary.latency_p50_ms ?? Number.POSITIVE_INFINITY;
  const sizeMb = summary.model_size_mb ?? 0;
  if (p95 <= 35 && sizeMb <= 80) {
    return {
      targetId: "raspberry_pi_5",
      label: "Raspberry Pi 5 ready",
      message: "Latency and size look suitable for compact ARM edge deployment.",
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
      message: "Usable locally, but likely too heavy for small single-board devices.",
    };
  }
  return {
    targetId: "desktop_gpu",
    label: "GPU target recommended",
    message: "Latency is high enough that GPU acceleration or a smaller model is advisable.",
  };
}

export interface DeploymentAdviseResult {
  target_profile: string;
  model_path: string;
  format: string;
  model_size_mb: number;
  compatibility_preflight: { compatible: boolean; details: string };
  quantization_recommendation: string;
  readiness_score: number;
  parity_check: {
    checked: boolean;
    max_coordinate_diff: number;
    class_match_rate: number;
    details: string;
  };
  benchmark_results: {
    latency_p50_ms: number;
    latency_p95_ms: number;
    throughput_fps: number;
    peak_memory_mb: number;
    benchmarked_locally: boolean;
  };
  risk_warnings: string[];
  runtime_snippets: Record<string, string>;
  report_path: string;
}

export interface ExportRequestInput {
  checkpoint: string;
  format: "onnx" | "tflite";
  quantize: boolean;
  calibrationDataset: string;
  outputPath: string;
  verifyParity: boolean;
}

export interface ExportRequest {
  tool: "quantize_int8" | "export_onnx" | "export_tflite";
  payload: Record<string, unknown>;
}

export function buildExportRequest(input: ExportRequestInput): ExportRequest {
  const outputPath = input.outputPath || undefined;
  if (input.format === "onnx" && input.quantize) {
    return {
      tool: "quantize_int8",
      payload: {
        checkpoint: input.checkpoint,
        calibration_dataset: input.calibrationDataset,
        output_path: outputPath,
      },
    };
  }
  if (input.format === "onnx") {
    return {
      tool: "export_onnx",
      payload: {
        checkpoint: input.checkpoint,
        output_path: outputPath,
        parity_check: input.verifyParity,
      },
    };
  }
  return {
    tool: "export_tflite",
    payload: { checkpoint: input.checkpoint, output_path: outputPath, int8: input.quantize },
  };
}

export function extractArtifactPath(payload: Record<string, unknown>): string | null {
  if (typeof payload["output_path"] === "string") return payload["output_path"];
  if (typeof payload["quantized_path"] === "string") return payload["quantized_path"];
  return null;
}

export function targetGroupLabel(group: string): string {
  switch (group) {
    case "cpu":
      return "CPU Targets";
    case "gpu":
      return "GPU Targets";
    case "edge":
      return "Edge Targets";
    case "mobile":
      return "Mobile Targets";
    default:
      return group;
  }
}

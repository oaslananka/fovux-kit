import { describe, expect, it } from "vitest";

import {
  buildExportRequest,
  extractArtifactPath,
  EXPORT_TARGETS,
  recommendExportTarget,
  suggestExportPath,
  targetGroupLabel,
} from "../../src/webviews/exportWizard/targets";

describe("export wizard targets", () => {
  it("maps known devices to export profiles", () => {
    expect(EXPORT_TARGETS.map((target) => target.id)).toEqual(
      expect.arrayContaining(["desktop_cpu", "desktop_gpu", "raspberry_pi_5", "jetson_nano"])
    );
  });

  it("suggests an artifact path under FOVUX_HOME exports", () => {
    expect(
      suggestExportPath("C:\\models\\yolov8n.pt", "C:\\Users\\Admin\\.fovux", "onnx", false)
    ).toContain("exports");
  });

  it("uses latency and model size to recommend an edge target", () => {
    expect(recommendExportTarget({ latency_p95_ms: 24, model_size_mb: 18 }).targetId).toBe(
      "raspberry_pi_5"
    );
    expect(recommendExportTarget({ latency_p95_ms: 180, model_size_mb: 320 }).targetId).toBe(
      "desktop_gpu"
    );
  });
  it("builds export tool requests without UI state coupling", () => {
    expect(
      buildExportRequest({
        checkpoint: "/models/best.pt",
        format: "onnx",
        quantize: true,
        calibrationDataset: "/data/dataset.yaml",
        outputPath: "/exports/best-int8.onnx",
        verifyParity: false,
      })
    ).toEqual({
      tool: "quantize_int8",
      payload: {
        checkpoint: "/models/best.pt",
        calibration_dataset: "/data/dataset.yaml",
        output_path: "/exports/best-int8.onnx",
      },
    });
  });

  it("extracts the exported artifact path from supported tool responses", () => {
    expect(extractArtifactPath({ output_path: "/exports/model.onnx" })).toBe(
      "/exports/model.onnx"
    );
    expect(extractArtifactPath({ quantized_path: "/exports/model-int8.onnx" })).toBe(
      "/exports/model-int8.onnx"
    );
    expect(extractArtifactPath({})).toBeNull();
  });

  it("covers export-path naming and separators", () => {
    expect(suggestExportPath("model.pt", "/tmp/fovux/", "tflite", true)).toBe(
      "/tmp/fovux/exports\\model-int8.tflite"
    );
    expect(suggestExportPath("model.pt", "C:\\fovux\\", "onnx", false)).toBe(
      "C:\\fovux\\exports\\model.onnx"
    );
  });

  it("covers all recommendation tiers and latency fallbacks", () => {
    expect(recommendExportTarget({ latency_p95_ms: 60, model_size_mb: 120 }).targetId).toBe(
      "jetson_nano"
    );
    expect(recommendExportTarget({ latency_p95_ms: 120, model_size_mb: 300 }).targetId).toBe(
      "desktop_cpu"
    );
    expect(recommendExportTarget({ latency_p50_ms: 20, model_size_mb: 10 }).targetId).toBe(
      "raspberry_pi_5"
    );
    expect(recommendExportTarget({}).targetId).toBe("desktop_gpu");
  });

  it("builds standard ONNX and TFLite requests", () => {
    expect(
      buildExportRequest({
        checkpoint: "/models/best.pt",
        format: "onnx",
        quantize: false,
        calibrationDataset: "",
        outputPath: "",
        verifyParity: true,
      })
    ).toEqual({
      tool: "export_onnx",
      payload: {
        checkpoint: "/models/best.pt",
        output_path: undefined,
        parity_check: true,
      },
    });
    expect(
      buildExportRequest({
        checkpoint: "/models/best.pt",
        format: "tflite",
        quantize: true,
        calibrationDataset: "",
        outputPath: "/exports/best.tflite",
        verifyParity: false,
      })
    ).toEqual({
      tool: "export_tflite",
      payload: {
        checkpoint: "/models/best.pt",
        output_path: "/exports/best.tflite",
        int8: true,
      },
    });
  });

  it("labels target groups and preserves unknown groups", () => {
    expect(targetGroupLabel("cpu")).toBe("CPU Targets");
    expect(targetGroupLabel("gpu")).toBe("GPU Targets");
    expect(targetGroupLabel("edge")).toBe("Edge Targets");
    expect(targetGroupLabel("mobile")).toBe("Mobile Targets");
    expect(targetGroupLabel("custom")).toBe("custom");
  });

});

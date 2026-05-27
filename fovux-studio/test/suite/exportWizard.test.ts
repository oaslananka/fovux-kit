import { describe, expect, it } from "vitest";

import {
  EXPORT_TARGETS,
  recommendExportTarget,
  suggestExportPath,
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
});

import { isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ExportSettingsForm } from "../../src/webviews/exportWizard/components/ExportSettingsForm";
import type { ExportWizardModelArtifact } from "../../src/webviews/shared/types";

const MODEL: ExportWizardModelArtifact = {
  name: "best.pt",
  path: "/runs/best.pt",
  format: "pt",
  source: "training",
};

describe("export settings form", () => {
  it("renders CUDA availability, empty checkpoints, and parity controls", () => {
    const callbacks = { verify: vi.fn() };
    const markup = renderToStaticMarkup(
      <ExportSettingsForm
        targetDevice="jetson_nano"
        hasCuda={false}
        checkpoint=""
        exportableModels={[]}
        format="onnx"
        verifyParity
        quantize={false}
        runBenchmarkAfterExport={false}
        calibrationDataset=""
        outputPath=""
        isExportRunning={false}
        onTargetDeviceChange={vi.fn()}
        onCheckpointChange={vi.fn()}
        onFormatChange={vi.fn()}
        onVerifyParityChange={vi.fn()}
        onQuantizeChange={vi.fn()}
        onRunBenchmarkAfterExportChange={vi.fn()}
        onCalibrationDatasetChange={vi.fn()}
        onOutputPathChange={vi.fn()}
        onRunExport={vi.fn()}
      />
    );

    expect(markup).toContain("CUDA unavailable");
    expect(markup).toContain("CUDA was not detected");
    expect(markup).toContain("No .pt checkpoints available yet");
    expect(markup).toContain("Verify ONNX parity after export");
    expect(markup).not.toContain('aria-label="Calibration dataset"');
    expect(markup).toContain("Run export");

    const tree = ExportSettingsForm({
      targetDevice: "desktop_cpu",
      hasCuda: null,
      checkpoint: "",
      exportableModels: [],
      format: "onnx",
      verifyParity: true,
      quantize: false,
      runBenchmarkAfterExport: false,
      calibrationDataset: "",
      outputPath: "",
      isExportRunning: false,
      onTargetDeviceChange: vi.fn(),
      onCheckpointChange: vi.fn(),
      onFormatChange: vi.fn(),
      onVerifyParityChange: callbacks.verify,
      onQuantizeChange: vi.fn(),
      onRunBenchmarkAfterExportChange: vi.fn(),
      onCalibrationDatasetChange: vi.fn(),
      onOutputPathChange: vi.fn(),
      onRunExport: vi.fn(),
    });
    triggerChecked(tree, "Verify ONNX parity after export", false);
    expect(callbacks.verify).toHaveBeenCalledWith(false);
  });

  it("falls back to the default target profile for an unknown persisted target", () => {
    const markup = renderToStaticMarkup(
      <ExportSettingsForm
        targetDevice={"unknown-target" as never}
        hasCuda={null}
        checkpoint=""
        exportableModels={[]}
        format="onnx"
        verifyParity={false}
        quantize={false}
        runBenchmarkAfterExport={false}
        calibrationDataset=""
        outputPath=""
        isExportRunning={false}
        onTargetDeviceChange={vi.fn()}
        onCheckpointChange={vi.fn()}
        onFormatChange={vi.fn()}
        onVerifyParityChange={vi.fn()}
        onQuantizeChange={vi.fn()}
        onRunBenchmarkAfterExportChange={vi.fn()}
        onCalibrationDatasetChange={vi.fn()}
        onOutputPathChange={vi.fn()}
        onRunExport={vi.fn()}
      />
    );

    expect(markup).toContain("Balanced default for x86 inference on ONNX Runtime CPU.");
  });

  it("renders quantized settings and forwards form changes", () => {
    const callbacks = {
      target: vi.fn(),
      checkpoint: vi.fn(),
      format: vi.fn(),
      verify: vi.fn(),
      quantize: vi.fn(),
      benchmark: vi.fn(),
      calibration: vi.fn(),
      output: vi.fn(),
      run: vi.fn(),
    };
    const tree = ExportSettingsForm({
      targetDevice: "raspberry_pi_5",
      hasCuda: true,
      checkpoint: MODEL.path,
      exportableModels: [MODEL],
      format: "tflite",
      verifyParity: false,
      quantize: true,
      runBenchmarkAfterExport: true,
      calibrationDataset: "/data/calibration",
      outputPath: "/exports/model.tflite",
      isExportRunning: true,
      onTargetDeviceChange: callbacks.target,
      onCheckpointChange: callbacks.checkpoint,
      onFormatChange: callbacks.format,
      onVerifyParityChange: callbacks.verify,
      onQuantizeChange: callbacks.quantize,
      onRunBenchmarkAfterExportChange: callbacks.benchmark,
      onCalibrationDatasetChange: callbacks.calibration,
      onOutputPathChange: callbacks.output,
      onRunExport: callbacks.run,
    });
    const markup = renderToStaticMarkup(tree);

    expect(markup).toContain("best.pt · training");
    expect(markup).toContain('aria-label="Calibration dataset"');
    expect(markup).not.toContain("Verify ONNX parity after export");
    expect(markup).toContain("Exporting...");

    triggerValue(tree, "Target device", "desktop_cpu");
    triggerValue(tree, "Checkpoint", "/runs/other.pt");
    triggerValue(tree, "Target format", "onnx");
    triggerChecked(tree, "Enable INT8 quantization", false);
    triggerChecked(tree, "Run latency benchmark after export", false);
    triggerValue(tree, "Calibration dataset", "/data/new");
    triggerValue(tree, "Output path", "/exports/new.onnx");
    requireElement(
      tree,
      (element) =>
        element.type === "button" &&
        String((element.props as { children?: ReactNode }).children).includes("Exporting"),
      "run export button"
    ).props.onClick();

    expect(callbacks.target).toHaveBeenCalledWith("desktop_cpu");
    expect(callbacks.checkpoint).toHaveBeenCalledWith("/runs/other.pt");
    expect(callbacks.format).toHaveBeenCalledWith("onnx");
    expect(callbacks.quantize).toHaveBeenCalledWith(false);
    expect(callbacks.benchmark).toHaveBeenCalledWith(false);
    expect(callbacks.calibration).toHaveBeenCalledWith("/data/new");
    expect(callbacks.output).toHaveBeenCalledWith("/exports/new.onnx");
    expect(callbacks.run).toHaveBeenCalled();
  });
});

function triggerValue(root: ReactElement, label: string, value: string): void {
  const element = requireElement(
    root,
    (candidate) => (candidate.props as { "aria-label"?: string })["aria-label"] === label,
    label
  );
  (element.props as { onChange: (event: { target: { value: string } }) => void }).onChange({
    target: { value },
  });
}

function triggerChecked(root: ReactElement, label: string, checked: boolean): void {
  const element = requireElement(
    root,
    (candidate) => (candidate.props as { "aria-label"?: string })["aria-label"] === label,
    label
  );
  (element.props as { onChange: (event: { target: { checked: boolean } }) => void }).onChange({
    target: { checked },
  });
}

function requireElement(
  node: ReactNode,
  predicate: (element: ReactElement) => boolean,
  description: string
): ReactElement {
  const match = findElement(node, predicate);
  if (!match) throw new Error(`Missing ${description}`);
  return match;
}

function findElement(
  node: ReactNode,
  predicate: (element: ReactElement) => boolean
): ReactElement | null {
  if (Array.isArray(node)) {
    for (const child of node) {
      const match = findElement(child, predicate);
      if (match) return match;
    }
    return null;
  }
  if (!isValidElement(node)) return null;
  if (predicate(node)) return node;
  const children = (node.props as { children?: ReactNode }).children;
  for (const child of Array.isArray(children) ? children : [children]) {
    const match = findElement(child, predicate);
    if (match) return match;
  }
  return null;
}

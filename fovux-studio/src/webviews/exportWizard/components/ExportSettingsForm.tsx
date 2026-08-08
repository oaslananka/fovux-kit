import type { CSSProperties, JSX } from "react";

import type { ExportWizardModelArtifact } from "../../shared/types";
import {
  EXPORT_TARGETS,
  targetGroupLabel,
  type ExportTargetDevice,
} from "../targets";

interface ExportSettingsFormProps {
  targetDevice: ExportTargetDevice;
  hasCuda: boolean | null;
  checkpoint: string;
  exportableModels: ExportWizardModelArtifact[];
  format: "onnx" | "tflite";
  verifyParity: boolean;
  quantize: boolean;
  runBenchmarkAfterExport: boolean;
  calibrationDataset: string;
  outputPath: string;
  isExportRunning: boolean;
  onTargetDeviceChange: (value: ExportTargetDevice) => void;
  onCheckpointChange: (value: string) => void;
  onFormatChange: (value: "onnx" | "tflite") => void;
  onVerifyParityChange: (value: boolean) => void;
  onQuantizeChange: (value: boolean) => void;
  onRunBenchmarkAfterExportChange: (value: boolean) => void;
  onCalibrationDatasetChange: (value: string) => void;
  onOutputPathChange: (value: string) => void;
  onRunExport: () => void;
}

const TARGET_GROUPS = ["cpu", "gpu", "edge", "mobile"] as const;

export function ExportSettingsForm({
  targetDevice,
  hasCuda,
  checkpoint,
  exportableModels,
  format,
  verifyParity,
  quantize,
  runBenchmarkAfterExport,
  calibrationDataset,
  outputPath,
  isExportRunning,
  onTargetDeviceChange,
  onCheckpointChange,
  onFormatChange,
  onVerifyParityChange,
  onQuantizeChange,
  onRunBenchmarkAfterExportChange,
  onCalibrationDatasetChange,
  onOutputPathChange,
  onRunExport,
}: Readonly<ExportSettingsFormProps>): JSX.Element {
  const targetProfile =
    EXPORT_TARGETS.find((target) => target.id === targetDevice) ?? EXPORT_TARGETS[0];

  return (
    <section style={formStyle}>
      <label style={fieldStyle}>
        <span>Target device</span>
        <select
          aria-label="Target device"
          style={inputStyle}
          value={targetDevice}
          onChange={(event) => onTargetDeviceChange(event.target.value as ExportTargetDevice)}
        >
          {TARGET_GROUPS.map((group) => (
            <optgroup key={group} label={targetGroupLabel(group)}>
              {EXPORT_TARGETS.filter((target) => target.group === group).map((target) => {
                const disabled = target.requiresCuda === true && hasCuda === false;
                return (
                  <option key={target.id} value={target.id} disabled={disabled}>
                    {target.label}
                    {disabled ? " (CUDA unavailable)" : ""}
                  </option>
                );
              })}
            </optgroup>
          ))}
        </select>
        <span style={helperTextStyle}>
          {targetProfile.description}
          {targetProfile.requiresCuda === true && hasCuda === false
            ? " CUDA was not detected, so this target is disabled."
            : ""}
        </span>
      </label>

      <label style={fieldStyle}>
        <span>Checkpoint</span>
        <select
          aria-label="Checkpoint"
          style={inputStyle}
          value={checkpoint}
          onChange={(event) => onCheckpointChange(event.target.value)}
          disabled={!exportableModels.length}
        >
          {!exportableModels.length ? (
            <option value="">No .pt checkpoints available yet</option>
          ) : null}
          {exportableModels.map((model) => (
            <option key={model.path} value={model.path}>
              {model.name} · {model.source}
            </option>
          ))}
        </select>
      </label>

      <label style={fieldStyle}>
        <span>Target format</span>
        <select
          aria-label="Target format"
          style={inputStyle}
          value={format}
          onChange={(event) => onFormatChange(event.target.value as "onnx" | "tflite")}
        >
          <option value="onnx">ONNX</option>
          <option value="tflite">TFLite</option>
        </select>
      </label>

      {format === "onnx" && !quantize ? (
        <label style={checkboxStyle}>
          <input
            type="checkbox"
            aria-label="Verify ONNX parity after export"
            checked={verifyParity}
            onChange={(event) => onVerifyParityChange(event.target.checked)}
          />
          <span>Verify ONNX parity after export</span>
        </label>
      ) : null}

      <label style={checkboxStyle}>
        <input
          type="checkbox"
          aria-label="Enable INT8 quantization"
          checked={quantize}
          onChange={(event) => onQuantizeChange(event.target.checked)}
        />
        <span>Enable INT8 quantization</span>
      </label>

      <label style={checkboxStyle}>
        <input
          type="checkbox"
          aria-label="Run latency benchmark after export"
          checked={runBenchmarkAfterExport}
          onChange={(event) => onRunBenchmarkAfterExportChange(event.target.checked)}
        />
        <span>Run latency benchmark after export</span>
      </label>

      {quantize ? (
        <label style={fieldStyle}>
          <span>Calibration dataset</span>
          <input
            aria-label="Calibration dataset"
            style={inputStyle}
            value={calibrationDataset}
            onChange={(event) => onCalibrationDatasetChange(event.target.value)}
            placeholder="Path to a calibration dataset"
          />
        </label>
      ) : null}

      <label style={fieldStyle}>
        <span>Output path</span>
        <input
          aria-label="Output path"
          style={inputStyle}
          value={outputPath}
          onChange={(event) => onOutputPathChange(event.target.value)}
          placeholder="Optional explicit output path"
        />
      </label>

      <button
        type="button"
        style={buttonStyle}
        onClick={onRunExport}
        disabled={isExportRunning}
        aria-busy={isExportRunning}
      >
        {isExportRunning ? "Exporting..." : "Run export"}
      </button>
    </section>
  );
}

const formStyle: CSSProperties = {
  display: "grid",
  gap: "14px",
  padding: "20px",
  borderRadius: "18px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
  maxWidth: "720px",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
};

const checkboxStyle: CSSProperties = {
  display: "flex",
  gap: "10px",
  alignItems: "center",
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "10px 12px",
  borderRadius: "10px",
  border: "1px solid var(--vscode-input-border)",
  background: "var(--vscode-input-background)",
  color: "var(--vscode-input-foreground)",
  outline: "none",
};

const buttonStyle: CSSProperties = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid var(--vscode-button-border, var(--vscode-panel-border))",
  background: "var(--vscode-button-background)",
  color: "var(--vscode-button-foreground)",
  cursor: "pointer",
  justifySelf: "start",
};

const helperTextStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: "12px",
};

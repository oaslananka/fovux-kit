import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, JSX } from "react";
import { createRoot } from "react-dom/client";

import { invokeTool, type HttpClientConfig } from "../shared/api";
import {
  EXPORT_TARGETS,
  recommendExportTarget,
  type BenchmarkSummary,
  type ExportRecommendation,
  type ExportTargetDevice,
  suggestExportPath,
} from "./targets";
import {
  ExportWizardInitialState,
  ExportWizardModelArtifact,
  postToExtension,
  readInitialState,
} from "../shared/types";

function ExportWizardApp(): JSX.Element {
  const initial = readInitialState<ExportWizardInitialState>({
    baseUrl: "http://127.0.0.1:7823",
    authToken: null,
    initialModels: [],
    fovuxHome: "",
    initialError: "Initial export wizard state was not provided.",
    isServerReachable: false,
  });
  const clientConfig = useMemo<HttpClientConfig>(
    () => ({ baseUrl: initial.baseUrl, authToken: initial.authToken }),
    [initial.authToken, initial.baseUrl]
  );
  const [models, setModels] = useState<ExportWizardModelArtifact[]>(initial.initialModels);
  const [checkpoint, setCheckpoint] = useState("");
  const [targetDevice, setTargetDevice] = useState<ExportTargetDevice>("desktop_cpu");
  const [format, setFormat] = useState<"onnx" | "tflite">("onnx");
  const [quantize, setQuantize] = useState(false);
  const [verifyParity, setVerifyParity] = useState(false);
  const [runBenchmarkAfterExport, setRunBenchmarkAfterExport] = useState(false);
  const [outputPath, setOutputPath] = useState("");
  const [calibrationDataset, setCalibrationDataset] = useState("");
  const [resultPath, setResultPath] = useState<string | null>(null);
  const [recommendation, setRecommendation] = useState<ExportRecommendation | null>(null);
  const [benchmarkError, setBenchmarkError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(initial.initialError);
  const [status, setStatus] = useState<string | null>(null);
  const [isExportRunning, setIsExportRunning] = useState(false);
  const exportRunningRef = useRef(false);
  const [hasCuda, setHasCuda] = useState<boolean | null>(null);
  const exportableModels = useMemo(
    () => models.filter((model) => model.format.toLowerCase() === "pt"),
    [models]
  );
  const targetProfile = useMemo(
    () => EXPORT_TARGETS.find((target) => target.id === targetDevice) ?? EXPORT_TARGETS[0],
    [targetDevice]
  );

  useEffect(() => {
    if (!initial.isServerReachable) {
      return;
    }

    const loadModels = async (): Promise<void> => {
      try {
        const response = await invokeTool<{
          models: ExportWizardModelArtifact[];
        }>(clientConfig, "model_list", {});
        setModels(response.models);
        const nextExportableModels = response.models.filter(
          (model) => model.format.toLowerCase() === "pt"
        );
        if (!checkpoint && nextExportableModels.length) {
          setCheckpoint(nextExportableModels[0].path);
        }
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : String(nextError));
      }
    };

    void loadModels();
  }, [checkpoint, clientConfig, initial.isServerReachable]);

  useEffect(() => {
    if (!initial.isServerReachable) {
      return;
    }
    const loadDoctor = async (): Promise<void> => {
      try {
        const report = await invokeTool<{
          gpu?: { accelerator?: string; available?: boolean };
        }>(clientConfig, "fovux_doctor", {});
        setHasCuda(report.gpu?.available === true && report.gpu?.accelerator === "cuda");
      } catch {
        setHasCuda(false);
      }
    };
    void loadDoctor();
  }, [clientConfig, initial.isServerReachable]);

  useEffect(() => {
    if (!exportableModels.length) {
      return;
    }
    if (!exportableModels.some((model) => model.path === checkpoint)) {
      setCheckpoint(exportableModels[0].path);
    }
  }, [checkpoint, exportableModels]);

  useEffect(() => {
    setFormat(targetProfile.format);
    setQuantize(targetProfile.quantize);
    setVerifyParity(targetProfile.verifyParity);
  }, [targetProfile]);

  useEffect(() => {
    if (!checkpoint || outputPath.trim()) {
      return;
    }
    setOutputPath(suggestExportPath(checkpoint, initial.fovuxHome, format, quantize));
  }, [checkpoint, format, initial.fovuxHome, outputPath, quantize]);

  return (
    <main style={pageStyle}>
      <header style={headerStyle}>
        <div>
          <p style={eyebrowStyle}>Export Wizard</p>
          <h1 style={titleStyle}>Ship the right artifact for edge deployment</h1>
        </div>
        <span style={badgeStyle}>{exportableModels.length} exportable checkpoints</span>
      </header>

      {!initial.isServerReachable ? (
        <section style={helperCardStyle}>
          <strong>HTTP server offline</strong>
          <p style={helperTextStyle}>
            Start the local Fovux server from VS Code to browse checkpoints and exports.
          </p>
          <button
            type="button"
            style={buttonStyle}
            onClick={() => postToExtension({ type: "startServer" })}
          >
            Start Fovux Server
          </button>
        </section>
      ) : null}

      {error ? <p style={errorStyle}>{error}</p> : null}
      {status ? <p style={successStyle}>{status}</p> : null}
      {benchmarkError ? <p style={errorStyle}>{benchmarkError}</p> : null}

      <section style={formStyle}>
        <label style={fieldStyle}>
          <span>Target device</span>
          <select
            aria-label="Target device"
            style={inputStyle}
            value={targetDevice}
            onChange={(event) => setTargetDevice(event.target.value as ExportTargetDevice)}
          >
            {["cpu", "gpu", "edge", "mobile"].map((group) => (
              <optgroup key={group} label={targetGroupLabel(group)}>
                {EXPORT_TARGETS.filter((target) => target.group === group).map((target) => {
                  const disabled = target.requiresCuda && hasCuda === false;
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
            {targetProfile.requiresCuda && hasCuda === false
              ? " CUDA was not detected by fovux_doctor, so this target is disabled."
              : ""}
          </span>
        </label>

        <label style={fieldStyle}>
          <span>Checkpoint</span>
          <select
            aria-label="Checkpoint"
            style={inputStyle}
            value={checkpoint}
            onChange={(event) => setCheckpoint(event.target.value)}
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
            onChange={(event) => setFormat(event.target.value as "onnx" | "tflite")}
          >
            <option value="onnx">ONNX</option>
            <option value="tflite">TFLite</option>
          </select>
        </label>

        {format === "onnx" && !quantize ? (
          <label style={checkboxStyle}>
            <input
              type="checkbox"
              checked={verifyParity}
              onChange={(event) => setVerifyParity(event.target.checked)}
            />
            <span>Verify ONNX parity after export</span>
          </label>
        ) : null}

        <label style={checkboxStyle}>
          <input
            type="checkbox"
            checked={quantize}
            onChange={(event) => setQuantize(event.target.checked)}
          />
          <span>Enable INT8 quantization</span>
        </label>

        <label style={checkboxStyle}>
          <input
            type="checkbox"
            checked={runBenchmarkAfterExport}
            onChange={(event) => setRunBenchmarkAfterExport(event.target.checked)}
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
              onChange={(event) => setCalibrationDataset(event.target.value)}
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
            onChange={(event) => setOutputPath(event.target.value)}
            placeholder="Optional explicit output path"
          />
        </label>

        <button
          type="button"
          style={buttonStyle}
          onClick={() => void runExport()}
          disabled={isExportRunning}
          aria-busy={isExportRunning}
        >
          Run export
        </button>
      </section>

      {!exportableModels.length ? (
        <section style={helperCardStyle}>
          <strong>Nothing to export yet</strong>
          <p style={helperTextStyle}>
            Finish a training run or add a .pt checkpoint under FOVUX_HOME before exporting.
            Existing ONNX/TFLite artifacts are shown in the Models and Exports views, but they are
            not valid source checkpoints for a new export.
          </p>
        </section>
      ) : null}

      {resultPath ? (
        <section style={resultStyle}>
          <strong>Latest artifact</strong>
          <code style={codeStyle}>{resultPath}</code>
          <button
            type="button"
            style={secondaryButtonStyle}
            onClick={() => postToExtension({ type: "openPath", path: resultPath })}
          >
            Reveal in Explorer
          </button>
        </section>
      ) : null}

      {recommendation ? (
        <section style={resultStyle}>
          <strong>{recommendation.label}</strong>
          <span style={helperTextStyle}>{recommendation.message}</span>
        </section>
      ) : null}
    </main>
  );

  async function runExport(): Promise<void> {
    if (exportRunningRef.current) {
      return;
    }

    if (!checkpoint) {
      setError("Select a checkpoint first.");
      return;
    }

    if (quantize && !calibrationDataset) {
      setError("Provide a calibration dataset when INT8 quantization is enabled.");
      return;
    }

    try {
      exportRunningRef.current = true;
      setIsExportRunning(true);
      setError(null);
      setRecommendation(null);
      setBenchmarkError(null);
      setStatus("Export running...");
      const payload = await selectTool();
      const artifactPath =
        typeof payload["output_path"] === "string"
          ? payload["output_path"]
          : typeof payload["quantized_path"] === "string"
            ? payload["quantized_path"]
            : null;
      setResultPath(artifactPath);
      let benchmarkSucceeded = true;
      if (runBenchmarkAfterExport) {
        if (!artifactPath) {
          benchmarkSucceeded = false;
          setBenchmarkError(
            "Latency benchmark could not run because export did not return an artifact path."
          );
        } else {
          benchmarkSucceeded = await benchmarkRecommendation(artifactPath);
        }
      }
      setStatus(
        benchmarkSucceeded
          ? "Export completed successfully."
          : "Export completed successfully, but the latency benchmark failed."
      );
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setStatus(null);
    } finally {
      exportRunningRef.current = false;
      setIsExportRunning(false);
    }
  }

  async function selectTool(): Promise<Record<string, unknown>> {
    if (format === "onnx" && quantize) {
      return invokeTool<Record<string, unknown>>(clientConfig, "quantize_int8", {
        checkpoint,
        calibration_dataset: calibrationDataset,
        output_path: outputPath || undefined,
        confirm: true,
      });
    }

    if (format === "onnx") {
      return invokeTool<Record<string, unknown>>(clientConfig, "export_onnx", {
        checkpoint,
        output_path: outputPath || undefined,
        parity_check: verifyParity,
        confirm: true,
      });
    }

    return invokeTool<Record<string, unknown>>(clientConfig, "export_tflite", {
      checkpoint,
      output_path: outputPath || undefined,
      int8: quantize,
      confirm: true,
    });
  }

  async function benchmarkRecommendation(artifactPath: string): Promise<boolean> {
    try {
      const benchmark = await invokeTool<BenchmarkSummary>(clientConfig, "benchmark_latency", {
        model_path: artifactPath,
        backend: targetProfile.benchmarkBackend ?? (format === "tflite" ? "tflite" : "onnxruntime"),
        num_warmup: 2,
        num_iterations: 5,
        confirm: true,
      });
      setRecommendation(recommendExportTarget(benchmark));
      return true;
    } catch (nextError) {
      setRecommendation(null);
      const message = nextError instanceof Error ? nextError.message : String(nextError);
      setBenchmarkError(`Latency benchmark failed: ${message}`);
      return false;
    }
  }
}

function targetGroupLabel(group: string): string {
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

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "24px",
  boxSizing: "border-box",
  background:
    "linear-gradient(135deg, var(--vscode-editorWidget-background), var(--vscode-editor-background) 50%)",
  color: "var(--vscode-editor-foreground)",
  fontFamily: "var(--vscode-font-family)",
  display: "grid",
  gap: "16px",
  alignContent: "start",
  alignItems: "start",
};

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "start",
};

const eyebrowStyle: CSSProperties = {
  margin: "0 0 6px 0",
  color: "var(--vscode-charts-orange)",
  fontSize: "12px",
  letterSpacing: "0.12em",
  textTransform: "uppercase",
};

const titleStyle: CSSProperties = {
  margin: 0,
  fontSize: "30px",
  lineHeight: "1.15",
};

const badgeStyle: CSSProperties = {
  padding: "10px 14px",
  borderRadius: "999px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editorWidget-background)",
};

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

const secondaryButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "var(--vscode-editorWidget-background)",
  color: "var(--vscode-editor-foreground)",
};

const resultStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  padding: "16px",
  borderRadius: "16px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
  maxWidth: "720px",
};

const codeStyle: CSSProperties = {
  padding: "10px 12px",
  borderRadius: "10px",
  background: "var(--vscode-editorWidget-background)",
  overflowX: "auto",
};

const errorStyle: CSSProperties = {
  padding: "12px 16px",
  borderRadius: "12px",
  background: "var(--vscode-inputValidation-errorBackground)",
  border: "1px solid var(--vscode-inputValidation-errorBorder)",
};

const successStyle: CSSProperties = {
  padding: "12px 16px",
  borderRadius: "12px",
  background: "var(--vscode-inputValidation-infoBackground)",
  border: "1px solid var(--vscode-inputValidation-infoBorder)",
};

const helperCardStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
  padding: "16px",
  borderRadius: "16px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
  maxWidth: "720px",
};

const helperTextStyle: CSSProperties = {
  margin: 0,
  color: "var(--vscode-descriptionForeground)",
  fontSize: "13px",
  lineHeight: "1.5",
};

const rootNode = document.getElementById("root");
if (rootNode) {
  createRoot(rootNode).render(<ExportWizardApp />);
}

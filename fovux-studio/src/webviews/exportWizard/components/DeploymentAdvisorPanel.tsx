import type { CSSProperties, JSX } from "react";

import type { ExportWizardModelArtifact } from "../../shared/types";
import type { DeploymentAdviseResult } from "../targets";

export interface DeploymentAdvisorPanelProps {
  models: ExportWizardModelArtifact[];
  modelPath: string;
  targetProfile: string;
  datasetPath: string;
  result: DeploymentAdviseResult | null;
  isRunning: boolean;
  snippetTab: string;
  onModelPathChange: (path: string) => void;
  onTargetProfileChange: (profile: string) => void;
  onDatasetPathChange: (path: string) => void;
  onSnippetTabChange: (tab: string) => void;
  onRun: () => void;
  onOpenPath: (path: string) => void;
}

export function DeploymentAdvisorPanel({
  models,
  modelPath,
  targetProfile,
  datasetPath,
  result,
  isRunning,
  snippetTab,
  onModelPathChange,
  onTargetProfileChange,
  onDatasetPathChange,
  onSnippetTabChange,
  onRun,
  onOpenPath,
}: DeploymentAdvisorPanelProps): JSX.Element {
  const scoreColor = readinessScoreColor(result?.readiness_score);

  return (
    <>
      <section style={formStyle}>
        <label style={fieldStyle}>
          <span>Select Model Artifact</span>
          <select
            aria-label="Select Model"
            style={inputStyle}
            value={modelPath}
            onChange={(event) => onModelPathChange(event.target.value)}
            disabled={!models.length}
          >
            {!models.length ? <option value="">No models available</option> : null}
            {models.map((model) => (
              <option key={model.path} value={model.path}>
                {model.name} · {model.format.toUpperCase()} ({model.source})
              </option>
            ))}
          </select>
        </label>

        <label style={fieldStyle}>
          <span>Deployment Target Profile</span>
          <select
            aria-label="Target Profile"
            style={inputStyle}
            value={targetProfile}
            onChange={(event) => onTargetProfileChange(event.target.value)}
          >
            <option value="cpu_server">CPU Server (onnxruntime)</option>
            <option value="nvidia_gpu_tensorrt">NVIDIA GPU / TensorRT</option>
            <option value="jetson">Jetson Embedded GPU</option>
            <option value="raspberry_pi">Raspberry Pi (TFLite/ONNX)</option>
            <option value="android_tflite">Android (TFLite)</option>
            <option value="browser_wasm">Browser / WASM runtime</option>
          </select>
        </label>

        <label style={fieldStyle}>
          <span>Validation Dataset Path (Optional parity check)</span>
          <input
            aria-label="Validation Dataset"
            style={inputStyle}
            value={datasetPath}
            onChange={(event) => onDatasetPathChange(event.target.value)}
            placeholder="e.g. C:\\Users\\Admin\\Desktop\\data\\coco_mini"
          />
        </label>

        <button
          type="button"
          style={buttonStyle}
          onClick={onRun}
          disabled={isRunning || !models.length}
        >
          {isRunning ? "Analyzing..." : "Run Deployment Advisor"}
        </button>
      </section>

      {result ? (
        <section style={resultStyle}>
          <div style={advisorResultHeaderStyle}>
            <div>
              <strong>Readiness Score</strong>
              <div style={{ ...readinessScoreStyle, color: scoreColor }}>
                {result.readiness_score}/100
              </div>
            </div>
            <button
              type="button"
              style={secondaryButtonStyle}
              onClick={() => onOpenPath(result.report_path)}
            >
              Reveal Markdown Report
            </button>
          </div>

          <div style={gridContainerStyle}>
            <div style={advisorDetailCardStyle}>
              <strong>Compatibility Checklist</strong>
              <div style={{ marginTop: "6px", fontSize: "13px" }}>
                Compatible:{" "}
                {result.compatibility_preflight.compatible ? (
                  <span style={checkSuccessStyle}>Yes</span>
                ) : (
                  <span style={checkFailStyle}>No</span>
                )}
              </div>
              <p style={{ ...helperTextStyle, marginTop: "6px" }}>
                {result.compatibility_preflight.details}
              </p>
            </div>

            <div style={advisorDetailCardStyle}>
              <strong>Quantization Recommendation</strong>
              <p style={{ ...helperTextStyle, marginTop: "8px" }}>
                {result.quantization_recommendation}
              </p>
            </div>
          </div>

          {result.risk_warnings.length > 0 ? (
            <div style={warningsContainerStyle}>
              <strong>Warnings &amp; Risks Detected</strong>
              {result.risk_warnings.map((warning, index) => (
                <div key={index} style={{ marginTop: "6px", fontSize: "13px" }}>
                  ⚠️ {warning}
                </div>
              ))}
            </div>
          ) : null}

          <div style={advisorDetailCardStyle}>
            <strong>Prediction Parity (Against PT Checkpoint)</strong>
            {result.parity_check.checked ? (
              <div style={{ marginTop: "6px", fontSize: "13px" }}>
                <div>
                  Max coordinate diff: <code>{result.parity_check.max_coordinate_diff}</code>
                </div>
                <div>
                  Class parity rate:{" "}
                  <code>{(result.parity_check.class_match_rate * 100).toFixed(0)}%</code>
                </div>
                <p style={{ ...helperTextStyle, marginTop: "4px" }}>
                  {result.parity_check.details}
                </p>
              </div>
            ) : (
              <p style={{ ...helperTextStyle, marginTop: "6px" }}>{result.parity_check.details}</p>
            )}
          </div>

          <div style={advisorDetailCardStyle}>
            <strong>Latency Benchmark Matrix</strong>
            <table style={benchmarkTableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>Metric</th>
                  <th style={thStyle}>Value</th>
                </tr>
              </thead>
              <tbody>
                <tr style={rowStyle}>
                  <td style={tdStyle}>Format</td>
                  <td style={tdStyle}>{result.format.toUpperCase()}</td>
                </tr>
                <tr style={rowStyle}>
                  <td style={tdStyle}>Model Size</td>
                  <td style={tdStyle}>{result.model_size_mb} MB</td>
                </tr>
                <tr style={rowStyle}>
                  <td style={tdStyle}>Latency (p50)</td>
                  <td style={tdStyle}>{result.benchmark_results.latency_p50_ms.toFixed(1)} ms</td>
                </tr>
                <tr style={rowStyle}>
                  <td style={tdStyle}>Latency (p95)</td>
                  <td style={tdStyle}>{result.benchmark_results.latency_p95_ms.toFixed(1)} ms</td>
                </tr>
                <tr style={rowStyle}>
                  <td style={tdStyle}>Throughput</td>
                  <td style={tdStyle}>{result.benchmark_results.throughput_fps.toFixed(1)} FPS</td>
                </tr>
                <tr style={rowStyle}>
                  <td style={tdStyle}>Peak Memory</td>
                  <td style={tdStyle}>{result.benchmark_results.peak_memory_mb.toFixed(1)} MB</td>
                </tr>
                <tr style={rowStyle}>
                  <td style={tdStyle}>Benchmarked Locally</td>
                  <td style={tdStyle}>
                    {result.benchmark_results.benchmarked_locally ? "Yes" : "Estimated"}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div style={advisorDetailCardStyle}>
            <strong>Integration Runtime Code Snippets</strong>
            <div style={snippetTabsContainerStyle}>
              {["python", "node", "docker"].map((tabName) => (
                <button
                  key={tabName}
                  type="button"
                  style={snippetTab === tabName ? activeSnippetTabStyle : snippetTabStyle}
                  onClick={() => onSnippetTabChange(tabName)}
                >
                  {tabName === "node" ? "Node.js" : tabName.toUpperCase()}
                </button>
              ))}
            </div>
            <div style={{ position: "relative", marginTop: "8px" }}>
              <button
                type="button"
                style={copyButtonStyle}
                onClick={() => {
                  const text = result.runtime_snippets[snippetTab] || "";
                  void navigator.clipboard.writeText(text);
                }}
              >
                Copy
              </button>
              <pre style={snippetPreStyle}>
                {result.runtime_snippets[snippetTab] || "Snippet not available"}
              </pre>
            </div>
          </div>
        </section>
      ) : null}
    </>
  );
}

function readinessScoreColor(score: number | undefined): string {
  if (score === undefined || score < 50) return "#ff6a3d";
  if (score >= 80) return "#00ffb4";
  return "var(--vscode-charts-orange)";
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

const secondaryButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "var(--vscode-editorWidget-background)",
  color: "var(--vscode-editor-foreground)",
};

const resultStyle: CSSProperties = {
  display: "grid",
  gap: "14px",
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

const advisorResultHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  borderBottom: "1px solid var(--vscode-panel-border)",
  paddingBottom: "12px",
};

const readinessScoreStyle: CSSProperties = {
  fontSize: "28px",
  fontWeight: "bold",
  marginTop: "4px",
};

const gridContainerStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: "12px",
};

const advisorDetailCardStyle: CSSProperties = {
  padding: "14px",
  borderRadius: "10px",
  background: "var(--vscode-editorWidget-background)",
  border: "1px solid var(--vscode-panel-border)",
};

const checkSuccessStyle: CSSProperties = {
  color: "#00ffb4",
  fontWeight: "bold",
};

const checkFailStyle: CSSProperties = {
  color: "#ff6a3d",
  fontWeight: "bold",
};

const warningsContainerStyle: CSSProperties = {
  padding: "14px",
  borderRadius: "10px",
  background: "rgba(255, 106, 61, 0.08)",
  border: "1px solid #ff6a3d",
};

const benchmarkTableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  marginTop: "8px",
  fontSize: "13px",
};

const thStyle: CSSProperties = {
  borderBottom: "1px solid var(--vscode-panel-border)",
  padding: "6px 8px",
  color: "var(--vscode-descriptionForeground)",
  textAlign: "left",
};

const rowStyle: CSSProperties = {
  borderBottom: "1px solid var(--vscode-panel-border)",
};

const tdStyle: CSSProperties = {
  padding: "6px 8px",
};

const snippetTabsContainerStyle: CSSProperties = {
  display: "flex",
  gap: "6px",
  marginTop: "8px",
  borderBottom: "1px solid var(--vscode-panel-border)",
  paddingBottom: "6px",
};

const snippetTabStyle: CSSProperties = {
  padding: "4px 8px",
  borderRadius: "4px",
  border: "none",
  background: "transparent",
  color: "var(--vscode-descriptionForeground)",
  cursor: "pointer",
  fontSize: "12px",
};

const activeSnippetTabStyle: CSSProperties = {
  ...snippetTabStyle,
  background: "rgba(255, 255, 255, 0.08)",
  color: "var(--vscode-editor-foreground)",
};

const snippetPreStyle: CSSProperties = {
  padding: "10px",
  borderRadius: "6px",
  background: "var(--vscode-sideBar-background)",
  border: "1px solid var(--vscode-panel-border)",
  fontFamily: "var(--vscode-editor-font-family, monospace)",
  fontSize: "12px",
  margin: 0,
  overflowX: "auto",
};

const copyButtonStyle: CSSProperties = {
  position: "absolute",
  right: "8px",
  top: "8px",
  padding: "4px 8px",
  borderRadius: "4px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editorWidget-background)",
  color: "var(--vscode-editor-foreground)",
  cursor: "pointer",
  fontSize: "11px",
};

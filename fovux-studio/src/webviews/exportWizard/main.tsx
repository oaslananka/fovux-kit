import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, JSX } from "react";
import { createRoot } from "react-dom/client";

import {
  invokeTool,
  requestChallenge,
  type ChallengeResponse,
  type HttpClientConfig,
} from "../shared/api";
import { ChallengeModal } from "../shared/ChallengeModal";
import {
  buildExportRequest,
  extractArtifactPath,
  EXPORT_TARGETS,
  recommendExportTarget,
  type BenchmarkSummary,
  type ExportRecommendation,
  type ExportTargetDevice,
  suggestExportPath,
  targetGroupLabel,
  type DeploymentAdviseResult,
} from "./targets";
import {
  ExportWizardInitialState,
  ExportWizardModelArtifact,
  postToExtension,
  readInitialState,
} from "../shared/types";

function ExportWizardApp(): JSX.Element {
  const [pendingChallenge, setPendingChallenge] = useState<{
    challenge: ChallengeResponse;
    resolve: (val: string) => void;
    reject: (err: Error) => void;
  } | null>(null);

  function confirmChallenge(challenge: ChallengeResponse): Promise<string> {
    return new Promise<string>((resolve, reject) => {
      setPendingChallenge({ challenge, resolve, reject });
    });
  }

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

  const [activeTab, setActiveTab] = useState<"export" | "advisor">("export");
  const [models, setModels] = useState<ExportWizardModelArtifact[]>(initial.initialModels);

  // Export state
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

  // Advisor state
  const [advisorModelPath, setAdvisorModelPath] = useState("");
  const [advisorTargetProfile, setAdvisorTargetProfile] = useState<string>("cpu_server");
  const [advisorDatasetPath, setAdvisorDatasetPath] = useState("");
  const [advisorResult, setAdvisorResult] = useState<DeploymentAdviseResult | null>(null);
  const [isAdvisorRunning, setIsAdvisorRunning] = useState(false);
  const [advisorSnippetTab, setAdvisorSnippetTab] = useState<string>("python");

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
        if (response.models.length > 0) {
          setAdvisorModelPath(response.models[0].path);
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
      const artifactPath = extractArtifactPath(payload);
      setResultPath(artifactPath);
      let benchmarkSucceeded = true;
      if (runBenchmarkAfterExport) {
        if (!artifactPath) {
          benchmarkSucceeded = false;
          setBenchmarkError("Latency benchmark failed: export did not return an artifact path.");
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
    const request = buildExportRequest({
      checkpoint,
      format,
      quantize,
      calibrationDataset,
      outputPath,
      verifyParity,
    });
    const challenge = await requestChallenge(clientConfig, request.tool, request.payload);
    const challengeId = await confirmChallenge(challenge);
    return invokeTool<Record<string, unknown>>(clientConfig, request.tool, {
      ...request.payload,
      challenge_id: challengeId,
    });
  }

  async function benchmarkRecommendation(artifactPath: string): Promise<boolean> {
    try {
      const payload = {
        model_path: artifactPath,
        backend: targetProfile.benchmarkBackend ?? (format === "tflite" ? "tflite" : "onnxruntime"),
        num_warmup: 2,
        num_iterations: 5,
      };
      const challenge = await requestChallenge(clientConfig, "benchmark_latency", payload);
      const challengeId = await confirmChallenge(challenge);
      const benchmark = await invokeTool<BenchmarkSummary>(clientConfig, "benchmark_latency", {
        ...payload,
        challenge_id: challengeId,
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

  async function runDeploymentAdvisor(): Promise<void> {
    if (!advisorModelPath) {
      setError("Select a model to analyze.");
      return;
    }
    try {
      setIsAdvisorRunning(true);
      setError(null);
      setAdvisorResult(null);

      const payload = {
        model_path: advisorModelPath,
        target_profile: advisorTargetProfile,
        dataset_path: advisorDatasetPath || undefined,
      };

      const result = await invokeTool<DeploymentAdviseResult>(
        clientConfig,
        "deployment_advise",
        payload
      );
      setAdvisorResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsAdvisorRunning(false);
    }
  }

  const scoreColor = useMemo(() => {
    if (!advisorResult) return "#ff6a3d";
    const score = advisorResult.readiness_score;
    if (score >= 80) return "#00ffb4";
    if (score >= 50) return "var(--vscode-charts-orange)";
    return "#ff6a3d";
  }, [advisorResult]);

  return (
    <main style={pageStyle}>
      <header style={headerStyle}>
        <div>
          <p style={eyebrowStyle}>Edge CV workbench</p>
          <h1 style={titleStyle}>
            {activeTab === "export" ? "Model Export Wizard" : "Deployment Advisor"}
          </h1>
        </div>
        <div style={tabContainerStyle}>
          <button
            type="button"
            style={activeTab === "export" ? activeTabStyle : tabStyle}
            onClick={() => {
              setActiveTab("export");
              setError(null);
            }}
          >
            Export Model
          </button>
          <button
            type="button"
            style={activeTab === "advisor" ? activeTabStyle : tabStyle}
            onClick={() => {
              setActiveTab("advisor");
              setError(null);
            }}
          >
            Deployment Advisor
          </button>
        </div>
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
      {status && activeTab === "export" ? <p style={successStyle}>{status}</p> : null}
      {benchmarkError && activeTab === "export" ? <p style={errorStyle}>{benchmarkError}</p> : null}

      {activeTab === "export" ? (
        <>
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
              {isExportRunning ? "Exporting..." : "Run export"}
            </button>
          </section>

          {!exportableModels.length ? (
            <section style={helperCardStyle}>
              <strong>Nothing to export yet</strong>
              <p style={helperTextStyle}>
                Finish a training run or add a .pt checkpoint under FOVUX_HOME.
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
        </>
      ) : (
        <>
          <section style={formStyle}>
            <label style={fieldStyle}>
              <span>Select Model Artifact</span>
              <select
                aria-label="Select Model"
                style={inputStyle}
                value={advisorModelPath}
                onChange={(e) => setAdvisorModelPath(e.target.value)}
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
                value={advisorTargetProfile}
                onChange={(e) => setAdvisorTargetProfile(e.target.value)}
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
                value={advisorDatasetPath}
                onChange={(e) => setAdvisorDatasetPath(e.target.value)}
                placeholder="e.g. C:\Users\Admin\Desktop\data\coco_mini"
              />
            </label>

            <button
              type="button"
              style={buttonStyle}
              onClick={() => void runDeploymentAdvisor()}
              disabled={isAdvisorRunning || !models.length}
            >
              {isAdvisorRunning ? "Analyzing..." : "Run Deployment Advisor"}
            </button>
          </section>

          {advisorResult ? (
            <section style={resultStyle}>
              <div style={advisorResultHeaderStyle}>
                <div>
                  <strong>Readiness Score</strong>
                  <div style={{ ...readinessScoreStyle, color: scoreColor }}>
                    {advisorResult.readiness_score}/100
                  </div>
                </div>
                <button
                  type="button"
                  style={secondaryButtonStyle}
                  onClick={() =>
                    postToExtension({ type: "openPath", path: advisorResult.report_path })
                  }
                >
                  Reveal Markdown Report
                </button>
              </div>

              {/* Compatibility & Quantization checklist */}
              <div style={gridContainerStyle}>
                <div style={advisorDetailCardStyle}>
                  <strong>Compatibility Checklist</strong>
                  <div style={{ marginTop: "6px", fontSize: "13px" }}>
                    Compatible:{" "}
                    {advisorResult.compatibility_preflight.compatible ? (
                      <span style={checkSuccessStyle}>Yes</span>
                    ) : (
                      <span style={checkFailStyle}>No</span>
                    )}
                  </div>
                  <p style={{ ...helperTextStyle, marginTop: "6px" }}>
                    {advisorResult.compatibility_preflight.details}
                  </p>
                </div>

                <div style={advisorDetailCardStyle}>
                  <strong>Quantization Recommendation</strong>
                  <p style={{ ...helperTextStyle, marginTop: "8px" }}>
                    {advisorResult.quantization_recommendation}
                  </p>
                </div>
              </div>

              {/* Risk Warnings */}
              {advisorResult.risk_warnings.length > 0 ? (
                <div style={warningsContainerStyle}>
                  <strong>Warnings &amp; Risks Detected</strong>
                  {advisorResult.risk_warnings.map((w, idx) => (
                    <div key={idx} style={{ marginTop: "6px", fontSize: "13px" }}>
                      ⚠️ {w}
                    </div>
                  ))}
                </div>
              ) : null}

              {/* Parity Check */}
              <div style={advisorDetailCardStyle}>
                <strong>Prediction Parity (Against PT Checkpoint)</strong>
                {advisorResult.parity_check.checked ? (
                  <div style={{ marginTop: "6px", fontSize: "13px" }}>
                    <div>
                      Max coordinate diff:{" "}
                      <code>{advisorResult.parity_check.max_coordinate_diff}</code>
                    </div>
                    <div>
                      Class parity rate:{" "}
                      <code>{(advisorResult.parity_check.class_match_rate * 100).toFixed(0)}%</code>
                    </div>
                    <p style={{ ...helperTextStyle, marginTop: "4px" }}>
                      {advisorResult.parity_check.details}
                    </p>
                  </div>
                ) : (
                  <p style={{ ...helperTextStyle, marginTop: "6px" }}>
                    {advisorResult.parity_check.details}
                  </p>
                )}
              </div>

              {/* Benchmarks Matrix */}
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
                      <td style={tdStyle}>{advisorResult.format.toUpperCase()}</td>
                    </tr>
                    <tr style={rowStyle}>
                      <td style={tdStyle}>Model Size</td>
                      <td style={tdStyle}>{advisorResult.model_size_mb} MB</td>
                    </tr>
                    <tr style={rowStyle}>
                      <td style={tdStyle}>Latency (p50)</td>
                      <td style={tdStyle}>
                        {advisorResult.benchmark_results.latency_p50_ms.toFixed(1)} ms
                      </td>
                    </tr>
                    <tr style={rowStyle}>
                      <td style={tdStyle}>Latency (p95)</td>
                      <td style={tdStyle}>
                        {advisorResult.benchmark_results.latency_p95_ms.toFixed(1)} ms
                      </td>
                    </tr>
                    <tr style={rowStyle}>
                      <td style={tdStyle}>Throughput</td>
                      <td style={tdStyle}>
                        {advisorResult.benchmark_results.throughput_fps.toFixed(1)} FPS
                      </td>
                    </tr>
                    <tr style={rowStyle}>
                      <td style={tdStyle}>Peak Memory</td>
                      <td style={tdStyle}>
                        {advisorResult.benchmark_results.peak_memory_mb.toFixed(1)} MB
                      </td>
                    </tr>
                    <tr style={rowStyle}>
                      <td style={tdStyle}>Benchmarked Locally</td>
                      <td style={tdStyle}>
                        {advisorResult.benchmark_results.benchmarked_locally ? "Yes" : "Estimated"}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Copy-Paste snippets */}
              <div style={advisorDetailCardStyle}>
                <strong>Integration Runtime Code Snippets</strong>
                <div style={snippetTabsContainerStyle}>
                  {["python", "node", "docker"].map((tabName) => (
                    <button
                      key={tabName}
                      type="button"
                      style={
                        advisorSnippetTab === tabName ? activeSnippetTabStyle : snippetTabStyle
                      }
                      onClick={() => setAdvisorSnippetTab(tabName)}
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
                      const text = advisorResult.runtime_snippets[advisorSnippetTab] || "";
                      void navigator.clipboard.writeText(text);
                    }}
                  >
                    Copy
                  </button>
                  <pre style={snippetPreStyle}>
                    {advisorResult.runtime_snippets[advisorSnippetTab] || "Snippet not available"}
                  </pre>
                </div>
              </div>
            </section>
          ) : null}
        </>
      )}
      <ChallengeModal
        challenge={pendingChallenge ? pendingChallenge.challenge : null}
        onConfirm={() => {
          if (pendingChallenge) {
            pendingChallenge.resolve(pendingChallenge.challenge.challenge_id);
            setPendingChallenge(null);
          }
        }}
        onCancel={() => {
          if (pendingChallenge) {
            pendingChallenge.reject(new Error("Operation cancelled."));
            setPendingChallenge(null);
          }
        }}
      />
    </main>
  );
}

// Styling CSS Properties
const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "24px",
  boxSizing: "border-box",
  background:
    "linear-gradient(135deg, var(--vscode-editorWidget-background), " +
    "var(--vscode-editor-background) 50%)",
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
  alignItems: "center",
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
  fontSize: "26px",
  fontWeight: "600",
  lineHeight: "1.15",
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
  fontSize: "13px",
  margin: 0,
};

const successStyle: CSSProperties = {
  padding: "12px 16px",
  borderRadius: "12px",
  background: "var(--vscode-inputValidation-infoBackground)",
  border: "1px solid var(--vscode-inputValidation-infoBorder)",
  fontSize: "13px",
  margin: 0,
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

const tabContainerStyle: CSSProperties = {
  display: "flex",
  gap: "8px",
};

const tabStyle: CSSProperties = {
  padding: "6px 12px",
  borderRadius: "6px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editorWidget-background)",
  color: "var(--vscode-editor-foreground)",
  cursor: "pointer",
  fontSize: "12px",
  fontWeight: "500",
};

const activeTabStyle: CSSProperties = {
  ...tabStyle,
  background: "var(--vscode-button-background)",
  color: "var(--vscode-button-foreground)",
  border: "1px solid var(--vscode-button-border, var(--vscode-panel-border))",
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

const rootNode = document.getElementById("root");
if (rootNode) {
  createRoot(rootNode).render(<ExportWizardApp />);
}

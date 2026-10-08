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
import { DeploymentAdvisorPanel } from "./components/DeploymentAdvisorPanel";
import { ExportSettingsForm } from "./components/ExportSettingsForm";
import {
  buildExportRequest,
  extractArtifactPath,
  EXPORT_TARGETS,
  recommendExportTarget,
  type BenchmarkSummary,
  type ExportRecommendation,
  type ExportTargetDevice,
  suggestExportPath,
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
          <ExportSettingsForm
            targetDevice={targetDevice}
            hasCuda={hasCuda}
            checkpoint={checkpoint}
            exportableModels={exportableModels}
            format={format}
            verifyParity={verifyParity}
            quantize={quantize}
            runBenchmarkAfterExport={runBenchmarkAfterExport}
            calibrationDataset={calibrationDataset}
            outputPath={outputPath}
            isExportRunning={isExportRunning}
            onTargetDeviceChange={setTargetDevice}
            onCheckpointChange={setCheckpoint}
            onFormatChange={setFormat}
            onVerifyParityChange={setVerifyParity}
            onQuantizeChange={setQuantize}
            onRunBenchmarkAfterExportChange={setRunBenchmarkAfterExport}
            onCalibrationDatasetChange={setCalibrationDataset}
            onOutputPathChange={setOutputPath}
            onRunExport={() => void runExport()}
          />

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
        <DeploymentAdvisorPanel
          models={models}
          modelPath={advisorModelPath}
          targetProfile={advisorTargetProfile}
          datasetPath={advisorDatasetPath}
          result={advisorResult}
          isRunning={isAdvisorRunning}
          snippetTab={advisorSnippetTab}
          onModelPathChange={setAdvisorModelPath}
          onTargetProfileChange={setAdvisorTargetProfile}
          onDatasetPathChange={setAdvisorDatasetPath}
          onSnippetTabChange={setAdvisorSnippetTab}
          onRun={() => void runDeploymentAdvisor()}
          onOpenPath={(path) => postToExtension({ type: "openPath", path })}
        />
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

const rootNode = document.getElementById("root");
if (rootNode) {
  createRoot(rootNode).render(<ExportWizardApp />);
}

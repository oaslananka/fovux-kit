import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, JSX } from "react";
import { createRoot } from "react-dom/client";

import { getRun, invokeTool, type HttpClientConfig } from "../shared/api";
import {
  estimateTrainingMinutes,
  TRAINING_PRESETS,
  type TrainingPreset,
} from "./presets";
import {
  postToExtension,
  readInitialState,
  type ExtensionToWebviewMessage,
  type TrainingLauncherInitialState,
  type UserPreset,
} from "../shared/types";

function TrainingLauncherApp(): JSX.Element {
  const initial = readInitialState<TrainingLauncherInitialState>({
    baseUrl: "http://127.0.0.1:7823",
    authToken: null,
    initialModels: [],
    fovuxHome: "",
    initialDatasetPath: "",
    initialError: "Initial training launcher state was not provided.",
    isServerReachable: false,
    userPresets: [],
  });
  const [authToken, setAuthToken] = useState<string | null>(initial.authToken);
  const clientConfig = useMemo<HttpClientConfig>(
    () => ({ baseUrl: initial.baseUrl, authToken }),
    [authToken, initial.baseUrl],
  );

  const [runName, setRunName] = useState("");
  const [datasetPath, setDatasetPath] = useState(initial.initialDatasetPath);
  const [model, setModel] = useState(
    initial.initialModels[0]?.path ?? "yolov8n.pt",
  );
  const [epochs, setEpochs] = useState(10);
  const [batch, setBatch] = useState(16);
  const [imgsz, setImgsz] = useState(640);
  const [device, setDevice] = useState("auto");
  const [tags, setTags] = useState("baseline");
  const [dryRun, setDryRun] = useState(false);
  const [force, setForce] = useState(false);
  const [maxConcurrentRuns, setMaxConcurrentRuns] = useState(1);
  const [extraArgs, setExtraArgs] = useState("{}");
  const [error, setError] = useState<string | null>(initial.initialError);
  const [status, setStatus] = useState<string | null>(null);
  const [userPresets, setUserPresets] = useState<UserPreset[]>(
    initial.userPresets,
  );
  const [presetImportJson, setPresetImportJson] = useState("");
  const [recentDatasets, setRecentDatasets] = useState<string[]>(() => {
    const raw = window.localStorage.getItem("fovux.recentDatasets");
    if (!raw) {
      return [];
    }
    try {
      const parsed = JSON.parse(raw) as unknown;
      return Array.isArray(parsed)
        ? parsed.filter((item): item is string => typeof item === "string")
        : [];
    } catch {
      return [];
    }
  });
  const roughEtaMinutes = useMemo(
    () => estimateTrainingMinutes(epochs, batch, imgsz),
    [batch, epochs, imgsz],
  );
  useEffect(() => {
    const listener = (event: MessageEvent<ExtensionToWebviewMessage>): void => {
      const message = event.data;
      if (!message || typeof message.type !== "string") {
        return;
      }
      if (message.type === "authTokenUpdated") {
        setAuthToken(message.authToken);
      }
      if (message.type === "userPresetsUpdated") {
        setUserPresets(message.presets);
      }
    };
    window.addEventListener("message", listener);
    return () => window.removeEventListener("message", listener);
  }, []);

  return (
    <main style={pageStyle}>
      <header style={headerStyle}>
        <p style={eyebrowStyle}>Training Launcher</p>
        <h1 style={titleStyle}>Start a YOLO run without leaving VS Code</h1>
        <p style={ledeStyle}>
          Pick a dataset, checkpoint, and edge-oriented defaults. Dry-run shows
          the exact tool payload before it launches anything.
        </p>
      </header>

      {!initial.isServerReachable ? (
        <section style={helperCardStyle}>
          <strong>HTTP server offline</strong>
          <p style={helperTextStyle}>
            Start the local Fovux server from VS Code, then launch training from
            this form.
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

      <section style={presetPanelStyle} aria-label="Training presets">
        <div style={titleRowStyle}>
          <strong>Presets</strong>
          <span style={mutedTextStyle}>
            Rough ETA: ~{roughEtaMinutes} minutes on a typical local
            workstation.
          </span>
        </div>
        <div style={presetGridStyle}>
          {TRAINING_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              style={presetButtonStyle}
              onClick={() => applyPreset(preset)}
            >
              <strong>{preset.label}</strong>
              <span style={helperTextStyle}>{preset.description}</span>
            </button>
          ))}
          {userPresets.map((preset) => (
            <div key={preset.name} style={userPresetStyle}>
              <button
                type="button"
                style={plainPresetButtonStyle}
                onClick={() => applyUserPreset(preset)}
              >
                <strong>{preset.name}</strong>
                <span style={helperTextStyle}>
                  {preset.config.model} · {preset.config.epochs} epochs · saved{" "}
                  {new Date(preset.createdAt).toLocaleDateString()}
                </span>
              </button>
              <button
                type="button"
                aria-label={`Delete preset ${preset.name}`}
                style={iconButtonStyle}
                onClick={() => {
                  setUserPresets((presets) =>
                    presets.filter(
                      (candidate) => candidate.name !== preset.name,
                    ),
                  );
                  postToExtension({
                    type: "deleteUserPreset",
                    name: preset.name,
                  });
                }}
              >
                x
              </button>
            </div>
          ))}
        </div>
        <div style={actionRowStyle}>
          <button
            type="button"
            style={secondaryButtonStyle}
            onClick={() => void importFromRun()}
          >
            Import from run
          </button>
          <button
            type="button"
            style={secondaryButtonStyle}
            onClick={() => postToExtension({ type: "exportUserPresets" })}
          >
            Export presets
          </button>
        </div>
        <label style={fieldStyle}>
          <span>Import preset JSON</span>
          <textarea
            aria-label="Import preset JSON"
            style={{ ...inputStyle, minHeight: 72 }}
            value={presetImportJson}
            onChange={(event) => setPresetImportJson(event.target.value)}
            placeholder='{"presets":[...]}'
          />
        </label>
        <button
          type="button"
          style={secondaryButtonStyle}
          onClick={() => importPresetJson()}
        >
          Import presets
        </button>
      </section>

      <section style={formStyle} aria-label="Training configuration">
        <label style={fieldStyle}>
          <span>Run name</span>
          <input
            aria-label="Run name"
            style={inputStyle}
            value={runName}
            onChange={(event) => setRunName(event.target.value)}
            placeholder="Optional stable run id"
          />
        </label>

        <label style={fieldStyle}>
          <span>Dataset path</span>
          <input
            aria-label="Dataset path"
            list="recent-datasets"
            style={inputStyle}
            value={datasetPath}
            onChange={(event) => setDatasetPath(event.target.value)}
            placeholder="C:\\path\\to\\dataset or /data/yolo"
          />
          <datalist id="recent-datasets">
            {recentDatasets.map((entry) => (
              <option key={entry} value={entry} />
            ))}
          </datalist>
        </label>

        <label style={fieldStyle}>
          <span>Model</span>
          <input
            aria-label="Model"
            list="known-models"
            style={inputStyle}
            value={model}
            onChange={(event) => setModel(event.target.value)}
          />
          <datalist id="known-models">
            <option value="yolov8n.pt" />
            <option value="yolo11n.pt" />
            {initial.initialModels.map((artifact) => (
              <option key={artifact.path} value={artifact.path} />
            ))}
          </datalist>
        </label>

        <div style={gridStyle}>
          <NumberField
            label="Epochs"
            value={epochs}
            onChange={setEpochs}
            min={1}
          />
          <NumberField
            label="Batch"
            value={batch}
            onChange={setBatch}
            min={1}
          />
          <NumberField
            label="Image size"
            value={imgsz}
            onChange={setImgsz}
            min={32}
          />
          <NumberField
            label="Max concurrent runs"
            value={maxConcurrentRuns}
            onChange={setMaxConcurrentRuns}
            min={0}
          />
        </div>

        <label style={fieldStyle}>
          <span>Device</span>
          <select
            aria-label="Device"
            style={inputStyle}
            value={device}
            onChange={(event) => setDevice(event.target.value)}
          >
            <option value="auto">Auto</option>
            <option value="cpu">CPU</option>
            <option value="0">CUDA device 0</option>
            <option value="mps">Apple Metal (MPS)</option>
          </select>
        </label>

        <label style={fieldStyle}>
          <span>Tags</span>
          <input
            aria-label="Tags"
            style={inputStyle}
            value={tags}
            onChange={(event) => setTags(event.target.value)}
            placeholder="baseline, edge, int8"
          />
        </label>

        <label style={fieldStyle}>
          <span>Extra Ultralytics args (JSON)</span>
          <textarea
            aria-label="Extra Ultralytics args"
            style={{ ...inputStyle, minHeight: 84 }}
            value={extraArgs}
            onChange={(event) => setExtraArgs(event.target.value)}
          />
        </label>

        <label style={checkboxStyle}>
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(event) => setDryRun(event.target.checked)}
          />
          <span>Dry-run only</span>
        </label>

        <label style={checkboxStyle}>
          <input
            type="checkbox"
            checked={force}
            onChange={(event) => setForce(event.target.checked)}
          />
          <span>
            Force overwrite an existing stopped, failed, or complete run
          </span>
        </label>

        <div style={actionRowStyle}>
          <button
            type="button"
            style={buttonStyle}
            onClick={() => void submit()}
          >
            {dryRun ? "Preview payload" : "Start training"}
          </button>
          <button
            type="button"
            style={secondaryButtonStyle}
            onClick={() => savePreset()}
          >
            Save preset
          </button>
        </div>
      </section>
    </main>
  );

  async function submit(): Promise<void> {
    try {
      setError(null);
      const payload = buildPayload();
      if (dryRun) {
        setStatus(JSON.stringify(payload, null, 2));
        return;
      }
      const candidateRunName = runName.trim();
      if (candidateRunName && !force && (await runExists(candidateRunName))) {
        setError(
          `'${candidateRunName}' already exists. Enable force overwrite or choose a different run name.`,
        );
        setStatus(null);
        return;
      }
      setStatus("Launching training run...");
      const result = await invokeTool<{ run_id: string; run_path: string }>(
        clientConfig,
        "train_start",
        payload,
      );
      const nextRecentDatasets = [
        datasetPath.trim(),
        ...recentDatasets.filter((entry) => entry !== datasetPath.trim()),
      ].slice(0, 5);
      setRecentDatasets(nextRecentDatasets);
      window.localStorage.setItem(
        "fovux.recentDatasets",
        JSON.stringify(nextRecentDatasets),
      );
      setStatus(`Started ${result.run_id}. Opening dashboard...`);
      postToExtension({ type: "openDashboard" });
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : String(nextError),
      );
      setStatus(null);
    }
  }

  function buildPayload(): Record<string, unknown> {
    if (!datasetPath.trim()) {
      throw new Error("Dataset path is required.");
    }
    let parsedExtra: Record<string, unknown> = {};
    if (extraArgs.trim()) {
      const raw = JSON.parse(extraArgs) as unknown;
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
        throw new Error("Extra args must be a JSON object.");
      }
      parsedExtra = raw as Record<string, unknown>;
    }
    return {
      dataset_path: datasetPath.trim(),
      model: model.trim(),
      epochs,
      batch,
      imgsz,
      device,
      tags: tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      extra_args: parsedExtra,
      name: runName.trim() || undefined,
      force,
      max_concurrent_runs: Math.max(0, Math.floor(maxConcurrentRuns)),
      confirm: true,
    };
  }

  async function runExists(name: string): Promise<boolean> {
    try {
      await getRun(clientConfig, name);
      return true;
    } catch {
      return false;
    }
  }

  function applyPreset(preset: TrainingPreset): void {
    setModel(preset.config.model);
    setEpochs(preset.config.epochs);
    setBatch(preset.config.batch);
    setImgsz(preset.config.imgsz);
    setDevice(preset.config.device);
    setTags(preset.config.tags);
    setStatus(`${preset.label} preset applied.`);
    setError(null);
  }

  function applyUserPreset(preset: UserPreset): void {
    setModel(preset.config.model);
    setEpochs(preset.config.epochs);
    setBatch(preset.config.batch);
    setImgsz(preset.config.imgsz);
    setDevice(preset.config.device);
    setTags(preset.config.tags);
    setExtraArgs(preset.config.extraArgs);
    setMaxConcurrentRuns(preset.config.maxConcurrentRuns);
    setStatus(`${preset.name} preset applied.`);
    setError(null);
  }

  function savePreset(): void {
    const name = runName.trim() || `Preset ${new Date().toLocaleString()}`;
    const preset: UserPreset = {
      name,
      createdAt: new Date().toISOString(),
      config: {
        model,
        epochs,
        batch,
        imgsz,
        device,
        tags,
        extraArgs,
        maxConcurrentRuns,
      },
    };
    setUserPresets((presets) => [
      preset,
      ...presets.filter((candidate) => candidate.name !== preset.name),
    ]);
    postToExtension({ type: "saveUserPreset", preset });
    setStatus(`${preset.name} preset saved.`);
  }

  async function importFromRun(): Promise<void> {
    const runId = runName.trim();
    if (!runId) {
      setError("Enter a run name or run ID before importing from a run.");
      return;
    }
    try {
      const run = await getRun(clientConfig, runId);
      if (run.dataset_path) {
        setDatasetPath(run.dataset_path);
      }
      setModel(run.model);
      setEpochs(run.epochs);
      setStatus(`Imported configuration from ${run.id}.`);
      setError(null);
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : String(nextError),
      );
    }
  }

  function importPresetJson(): void {
    try {
      const presets = parseImportedPresets(presetImportJson);
      if (!presets.length) {
        throw new Error("No valid presets found.");
      }
      setUserPresets((current) => mergePresets(presets, current));
      postToExtension({ type: "importUserPresets", presets });
      setPresetImportJson("");
      setStatus(
        `Imported ${presets.length} preset${presets.length === 1 ? "" : "s"}.`,
      );
      setError(null);
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : String(nextError),
      );
    }
  }
}

export function parseImportedPresets(rawJson: string): UserPreset[] {
  const parsed = JSON.parse(rawJson) as unknown;
  const candidates = Array.isArray(parsed)
    ? parsed
    : parsed &&
        typeof parsed === "object" &&
        Array.isArray((parsed as { presets?: unknown }).presets)
      ? (parsed as { presets: unknown[] }).presets
      : [];
  return candidates.filter(isUserPreset);
}

function isUserPreset(value: unknown): value is UserPreset {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Record<string, unknown>;
  const config = record["config"];
  if (!config || typeof config !== "object") {
    return false;
  }
  const cfg = config as Record<string, unknown>;
  return (
    typeof record["name"] === "string" &&
    typeof record["createdAt"] === "string" &&
    typeof cfg["model"] === "string" &&
    typeof cfg["epochs"] === "number" &&
    typeof cfg["batch"] === "number" &&
    typeof cfg["imgsz"] === "number" &&
    typeof cfg["device"] === "string" &&
    typeof cfg["tags"] === "string" &&
    typeof cfg["extraArgs"] === "string" &&
    typeof cfg["maxConcurrentRuns"] === "number"
  );
}

export function mergePresets(
  imported: UserPreset[],
  current: UserPreset[],
): UserPreset[] {
  return [
    ...imported,
    ...current.filter(
      (candidate) => !imported.some((preset) => preset.name === candidate.name),
    ),
  ].slice(0, 20);
}

function NumberField(props: {
  label: string;
  value: number;
  min: number;
  onChange: (value: number) => void;
}): JSX.Element {
  return (
    <label style={fieldStyle}>
      <span>{props.label}</span>
      <input
        aria-label={props.label}
        style={inputStyle}
        type="number"
        min={props.min}
        value={props.value}
        onChange={(event) => {
          const nextValue = Number(event.target.value);
          props.onChange(Number.isFinite(nextValue) ? nextValue : props.min);
        }}
      />
    </label>
  );
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "24px",
  boxSizing: "border-box",
  color: "var(--vscode-editor-foreground)",
  background:
    "radial-gradient(circle at top left, color-mix(in srgb, var(--vscode-charts-orange) 18%, transparent), transparent 34%), var(--vscode-editor-background)",
  fontFamily: "var(--vscode-font-family)",
  display: "grid",
  gap: 16,
  alignContent: "start",
  alignItems: "start",
};

const headerStyle: CSSProperties = {
  maxWidth: 820,
};

const eyebrowStyle: CSSProperties = {
  margin: "0 0 6px",
  color: "var(--vscode-charts-orange)",
  fontSize: 12,
  letterSpacing: "0.14em",
  textTransform: "uppercase",
};

const titleStyle: CSSProperties = {
  margin: 0,
  fontSize: 32,
  lineHeight: 1.12,
};

const ledeStyle: CSSProperties = {
  margin: "10px 0 0",
  color: "var(--vscode-descriptionForeground)",
  lineHeight: 1.55,
};

const formStyle: CSSProperties = {
  display: "grid",
  gap: 14,
  maxWidth: 820,
  padding: 20,
  borderRadius: 18,
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
  gap: 12,
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: 8,
};

const inputStyle: CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid var(--vscode-input-border)",
  background: "var(--vscode-input-background)",
  color: "var(--vscode-input-foreground)",
};

const checkboxStyle: CSSProperties = {
  display: "flex",
  gap: 10,
  alignItems: "center",
};

const presetPanelStyle: CSSProperties = {
  display: "grid",
  gap: 12,
  maxWidth: 820,
  padding: 18,
  borderRadius: 18,
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const titleRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  alignItems: "baseline",
  flexWrap: "wrap",
};

const presetGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: 12,
};

const presetButtonStyle: CSSProperties = {
  display: "grid",
  gap: 6,
  padding: 14,
  borderRadius: 14,
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editorWidget-background)",
  color: "var(--vscode-editor-foreground)",
  cursor: "pointer",
  textAlign: "left",
};

const userPresetStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 32px",
  gap: 8,
  padding: 10,
  borderRadius: 8,
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editorWidget-background)",
};

const plainPresetButtonStyle: CSSProperties = {
  display: "grid",
  gap: 6,
  padding: 0,
  border: 0,
  background: "transparent",
  color: "var(--vscode-editor-foreground)",
  cursor: "pointer",
  textAlign: "left",
};

const iconButtonStyle: CSSProperties = {
  width: 32,
  height: 32,
  borderRadius: 6,
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editor-background)",
  color: "var(--vscode-descriptionForeground)",
  cursor: "pointer",
};

const mutedTextStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: 12,
};

const buttonStyle: CSSProperties = {
  justifySelf: "start",
  padding: "10px 14px",
  borderRadius: 10,
  border: "1px solid var(--vscode-button-border, var(--vscode-panel-border))",
  background: "var(--vscode-button-background)",
  color: "var(--vscode-button-foreground)",
  cursor: "pointer",
};

const secondaryButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "var(--vscode-editorWidget-background)",
  color: "var(--vscode-editor-foreground)",
};

const actionRowStyle: CSSProperties = {
  display: "flex",
  gap: 10,
  flexWrap: "wrap",
};

const helperCardStyle: CSSProperties = {
  display: "grid",
  gap: 8,
  padding: 16,
  borderRadius: 16,
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
  maxWidth: 820,
};

const helperTextStyle: CSSProperties = {
  margin: 0,
  color: "var(--vscode-descriptionForeground)",
  lineHeight: 1.5,
};

const errorStyle: CSSProperties = {
  maxWidth: 820,
  padding: "12px 16px",
  borderRadius: 12,
  background: "var(--vscode-inputValidation-errorBackground)",
  border: "1px solid var(--vscode-inputValidation-errorBorder)",
};

const successStyle: CSSProperties = {
  maxWidth: 820,
  padding: "12px 16px",
  borderRadius: 12,
  whiteSpace: "pre-wrap",
  background: "var(--vscode-inputValidation-infoBackground)",
  border: "1px solid var(--vscode-inputValidation-infoBorder)",
};

const rootNode =
  typeof document === "undefined" ? null : document.getElementById("root");
if (rootNode) {
  createRoot(rootNode).render(<TrainingLauncherApp />);
}

import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, JSX } from "react";
import { createRoot } from "react-dom/client";

import { MetricChart, type ChartSeries } from "./components/MetricChart";
import { RunList } from "./components/RunList";
import type { HttpClientConfig, MetricPayload, RunSummary } from "../shared/api";
import { listRuns, subscribeToMetrics } from "../shared/api";
import { DashboardInitialState, postToExtension, readInitialState } from "../shared/types";

const COLORS = [
  "var(--vscode-charts-blue)",
  "var(--vscode-charts-orange)",
  "var(--vscode-charts-purple)",
  "var(--vscode-charts-green)",
  "var(--vscode-charts-red)",
];
const MAP50_KEYS = ["metrics/mAP50(B)", "map50", "mAP50", "metrics/map50", "metrics/mAP50"];
const BOX_LOSS_KEYS = ["train/box_loss", "loss/box", "box_loss", "box"];

interface NextAction {
  title: string;
  description: string;
  ctaText: string;
  type: "startServer" | "initializeDemoWorkspace" | "triggerCommand";
  command?: string;
  args?: unknown[];
}

function calculateNextAction(state: DashboardInitialState, hasRuns: boolean): NextAction {
  if (!state.isServerReachable) {
    return {
      title: "Start Fovux Local Server",
      description:
        "Connect Fovux Studio to the python-based MCP tool suite to begin model training and evaluation.",
      ctaText: "Start Server",
      type: "startServer",
    };
  }

  const hasDatasets = !!(state.discoveredDatasets && state.discoveredDatasets.length > 0);

  if (!hasRuns && !hasDatasets) {
    return {
      title: "Set Up a Demo Workspace",
      description:
        "Initialize a sample YOLO dataset, pre-trained base model, and mock run logs with just one click.",
      ctaText: "Initialize Demo Workspace",
      type: "initializeDemoWorkspace",
    };
  }

  if (hasDatasets && !hasRuns) {
    return {
      title: "Inspect Discovered Dataset",
      description:
        "A dataset yaml was detected in your workspace. Inspect classes, label health, and check splits.",
      ctaText: "Open Dataset Inspector",
      type: "triggerCommand",
      command: "fovux.openDatasetInspector",
      args: [state.discoveredDatasets?.[0]],
    };
  }

  const activeRun = state.initialRuns.find((r) => r.status === "running");
  if (activeRun) {
    return {
      title: "Monitor Active Training",
      description: `Run "${activeRun.id}" is currently training. Watch losses, live metric streams, and epoch curves.`,
      ctaText: "Focus Running Training",
      type: "triggerCommand",
      command: "fovux.openDashboard",
    };
  }

  return {
    title: "Export Finished Model",
    description:
      "Your YOLO training runs are complete. Package the model to ONNX or TFLite for edge deployment.",
    ctaText: "Open Export Wizard",
    type: "triggerCommand",
    command: "fovux.openExportWizard",
  };
}

function DashboardApp(): JSX.Element {
  const initial = readInitialState<DashboardInitialState>({
    baseUrl: "http://127.0.0.1:7823",
    authToken: null,
    pollIntervalMs: 2000,
    initialRuns: [],
    initialError: "Initial state not provided.",
    isServerReachable: false,
    fovuxHome: "",
    activeProfile: "default",
    availableProfiles: [],
    discoveredDatasets: [],
  });

  const clientConfig = useMemo<HttpClientConfig>(
    () => ({
      baseUrl: initial.baseUrl,
      authToken: initial.authToken,
    }),
    [initial.authToken, initial.baseUrl]
  );

  const [runs, setRuns] = useState<RunSummary[]>(initial.initialRuns);
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [seriesByRun, setSeriesByRun] = useState<Record<string, MetricPayload[]>>({});
  const [error, setError] = useState<string | null>(initial.initialError);

  useEffect(() => {
    let disposed = false;
    const refresh = async (): Promise<void> => {
      try {
        const nextRuns = await listRuns(clientConfig);
        if (!disposed) {
          setRuns(nextRuns);
          setError(null);
        }
      } catch (nextError) {
        if (!disposed) {
          setError(nextError instanceof Error ? nextError.message : String(nextError));
        }
      }
    };

    if (initial.isServerReachable) {
      void refresh();
    }
    const timer = window.setInterval(() => {
      if (initial.isServerReachable) {
        void refresh();
      }
    }, initial.pollIntervalMs);

    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [clientConfig, initial.pollIntervalMs, initial.isServerReachable]);

  useEffect(() => {
    if (!runs.length || selectedRunIds.length) {
      return;
    }
    setSelectedRunIds(runs.slice(0, Math.min(3, runs.length)).map((run) => run.id));
  }, [runs, selectedRunIds.length]);

  useEffect(() => {
    const activeRunIds = selectedRunIds.slice(0, 5);
    setSeriesByRun((current) =>
      Object.fromEntries(Object.entries(current).filter(([runId]) => activeRunIds.includes(runId)))
    );

    const unsubscribers = activeRunIds.map((runId) =>
      subscribeToMetrics(
        clientConfig,
        runId,
        (payload) => {
          setSeriesByRun((current) => ({
            ...current,
            [runId]: upsertPayload(current[runId] ?? [], payload),
          }));
        },
        (streamError) => setError(streamError)
      )
    );

    return () => {
      unsubscribers.forEach((unsubscribe) => unsubscribe());
    };
  }, [clientConfig, selectedRunIds]);

  const mapSeries = useMemo(
    () =>
      selectedRunIds
        .map((runId, index) => toChartSeries(runId, seriesByRun[runId] ?? [], MAP50_KEYS, index))
        .filter((series): series is ChartSeries => series !== null),
    [selectedRunIds, seriesByRun]
  );

  const lossSeries = useMemo(
    () =>
      selectedRunIds
        .map((runId, index) => toChartSeries(runId, seriesByRun[runId] ?? [], BOX_LOSS_KEYS, index))
        .filter((series): series is ChartSeries => series !== null),
    [selectedRunIds, seriesByRun]
  );

  const connectionStatus = initial.isServerReachable
    ? error
      ? "Metric stream degraded: reconnecting via polling fallback."
      : "Metric polling fallback active; dashboard will keep refreshing run state."
    : "Backend " + "disconnected: using cached/offline dashboard state until the local server reconnects.";

  const latestRows = selectedRunIds
    .map((runId) => seriesByRun[runId]?.at(-1))
    .filter((payload): payload is MetricPayload => payload !== undefined);

  const nextAction = useMemo(
    () => calculateNextAction(initial, runs.length > 0),
    [initial, runs.length]
  );

  const handleNextActionClick = () => {
    if (nextAction.type === "startServer") {
      postToExtension({ type: "startServer" });
    } else if (nextAction.type === "initializeDemoWorkspace") {
      postToExtension({ type: "initializeDemoWorkspace" });
    } else if (nextAction.type === "triggerCommand" && nextAction.command) {
      postToExtension({
        type: "triggerCommand",
        command: nextAction.command,
        args: nextAction.args,
      });
    }
  };

  const handleProfileChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const profile = initial.availableProfiles?.find((p) => p.name === e.target.value);
    if (profile) {
      postToExtension({ type: "selectFovuxProfile", profile });
    }
  };

  return (
    <main style={pageStyle}>
      <header style={heroStyle}>
        <div>
          <p style={eyebrowStyle}>Fovux Home</p>
          <h1 style={titleStyle}>Local Computer Vision Workbench</h1>
          <p style={subtitleStyle}>
            Configure datasets, launch and monitor YOLO training runs, evaluate model cards, and
            export optimized edge-AI deployment checkpoints.
          </p>
        </div>
        <div style={badgeStyle}>{runs.length} tracked runs</div>
      </header>

      {/* Grid of status cards */}
      <section style={overviewGridStyle}>
        {/* Status card */}
        <article style={statusCardStyle}>
          <div style={statusHeaderStyle}>
            <span
              style={{
                ...statusDotStyle,
                backgroundColor: initial.isServerReachable
                  ? "var(--vscode-charts-green)"
                  : "var(--vscode-charts-red)",
              }}
            />
            <strong style={cardTitleStyle}>Fovux Server</strong>
          </div>
          <span style={cardValueStyle}>{initial.isServerReachable ? "Online" : "Offline"}</span>
          <span style={cardSubtitleStyle}>{initial.baseUrl}</span>
        </article>

        {/* Profile card */}
        <article style={statusCardStyle}>
          <strong style={cardTitleStyle}>Active Workspace Profile</strong>
          {initial.availableProfiles && initial.availableProfiles.length > 0 ? (
            <select
              style={selectStyle}
              aria-label="Active Profile"
              value={initial.activeProfile ?? "default"}
              onChange={handleProfileChange}
            >
              {initial.availableProfiles.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name}
                </option>
              ))}
            </select>
          ) : (
            <span style={cardValueStyle}>{initial.activeProfile ?? "default"}</span>
          )}
          <span style={cardSubtitleStyle} title={initial.fovuxHome}>
            {initial.fovuxHome ? truncatePath(initial.fovuxHome) : "No FOVUX_HOME resolved"}
          </span>
        </article>

        {/* Token Status */}
        <article style={statusCardStyle}>
          <strong style={cardTitleStyle}>Auth Credentials</strong>
          <span style={cardValueStyle}>{initial.authToken ? "Active Session" : "None loaded"}</span>
          <span style={cardSubtitleStyle}>
            {initial.authToken ? "Bearer token active" : "Using local challenge fallback"}
          </span>
        </article>
      </section>

      <div style={twoColLayout}>
        {/* Left column: Guided wizard and Next action */}
        <div style={leftColStyle}>
          {/* Next Best Action Card */}
          <section style={nextActionCardStyle}>
            <h2 style={sectionHeaderStyle}>Next Recommended Action</h2>
            <h3 style={{ margin: "4px 0 8px 0", fontSize: "18px" }}>{nextAction.title}</h3>
            <p style={mutedParagraphStyle}>{nextAction.description}</p>
            <button type="button" style={primaryButtonStyle} onClick={handleNextActionClick}>
              {nextAction.ctaText}
            </button>
          </section>

          {/* Guided workflow wizard */}
          <section style={wizardCardStyle}>
            <h2 style={sectionHeaderStyle}>CV Workflow Guide</h2>
            <div style={wizardStepListStyle}>
              {/* Step 1 */}
              <div
                style={{
                  ...wizardStepItemStyle,
                  borderColor: initial.isServerReachable
                    ? "var(--vscode-charts-green)"
                    : "var(--vscode-panel-border)",
                }}
              >
                <div>
                  <strong>1. Start Server</strong>
                  <p style={mutedParagraphStyle}>Start python MCP tool service.</p>
                </div>
                {initial.isServerReachable ? (
                  <span style={checkmarkStyle}>✓</span>
                ) : (
                  <button
                    type="button"
                    style={smallButtonStyle}
                    onClick={() => postToExtension({ type: "startServer" })}
                  >
                    Start
                  </button>
                )}
              </div>

              {/* Step 2 */}
              <div
                style={{
                  ...wizardStepItemStyle,
                  borderColor:
                    runs.length > 0 ? "var(--vscode-charts-green)" : "var(--vscode-panel-border)",
                }}
              >
                <div>
                  <strong>2. Set Up Dataset / Demo</strong>
                  <p style={mutedParagraphStyle}>
                    Initialize workspace with demo assets or dataset.
                  </p>
                </div>
                {runs.length > 0 ? (
                  <span style={checkmarkStyle}>✓</span>
                ) : (
                  <button
                    type="button"
                    style={smallButtonStyle}
                    onClick={() => postToExtension({ type: "initializeDemoWorkspace" })}
                  >
                    Setup Demo
                  </button>
                )}
              </div>

              {/* Step 3 */}
              <div style={wizardStepItemStyle}>
                <div>
                  <strong>3. Inspect Dataset Health</strong>
                  <p style={mutedParagraphStyle}>
                    Check annotations and split validation statistics.
                  </p>
                </div>
                <button
                  type="button"
                  style={smallButtonStyle}
                  onClick={() =>
                    postToExtension({
                      type: "triggerCommand",
                      command: "fovux.openDatasetInspector",
                      args: [initial.discoveredDatasets?.[0]],
                    })
                  }
                >
                  Inspect
                </button>
              </div>

              {/* Step 4 */}
              <div style={wizardStepItemStyle}>
                <div>
                  <strong>4. Start Training</strong>
                  <p style={mutedParagraphStyle}>Launch non-blocking YOLO training runs.</p>
                </div>
                <button
                  type="button"
                  style={smallButtonStyle}
                  onClick={() =>
                    postToExtension({
                      type: "triggerCommand",
                      command: "fovux.startTraining",
                      args: [initial.discoveredDatasets?.[0]],
                    })
                  }
                >
                  Train
                </button>
              </div>

              {/* Step 5 */}
              <div style={wizardStepItemStyle}>
                <div>
                  <strong>5. Export & Evaluate</strong>
                  <p style={mutedParagraphStyle}>
                    Optimize checkpoints for ONNX or TFLite target deploy.
                  </p>
                </div>
                <button
                  type="button"
                  style={smallButtonStyle}
                  onClick={() =>
                    postToExtension({
                      type: "triggerCommand",
                      command: "fovux.openExportWizard",
                    })
                  }
                >
                  Export
                </button>
              </div>
            </div>
          </section>

          {/* Discovered datasets */}
          <section style={wizardCardStyle}>
            <h2 style={sectionHeaderStyle}>Discovered Datasets</h2>
            {initial.discoveredDatasets && initial.discoveredDatasets.length > 0 ? (
              <div style={datasetListStyle}>
                {initial.discoveredDatasets.map((d) => (
                  <div key={d} style={datasetItemStyle}>
                    <span style={datasetIconStyle}>📁</span>
                    <div style={{ flex: 1 }}>
                      <strong style={{ fontSize: "13px" }}>{getBasename(d)}</strong>
                      <div
                        style={{
                          fontSize: "11px",
                          color: "var(--vscode-descriptionForeground)",
                        }}
                      >
                        {d}
                      </div>
                    </div>
                    <button
                      type="button"
                      style={smallButtonStyle}
                      onClick={() =>
                        postToExtension({
                          type: "triggerCommand",
                          command: "fovux.openDatasetInspector",
                          args: [d],
                        })
                      }
                    >
                      Inspect
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ ...mutedParagraphStyle, margin: "8px 0" }}>
                No datasets (data.yaml files) found in your workspace folders.
              </p>
            )}
          </section>
        </div>

        {/* Right column: active runs, charts */}
        <div style={rightColStyle}>
          <p style={resilienceStatusStyle}>{connectionStatus}</p>
          {error ? <p style={errorStyle}>{error}</p> : null}

          {runs.length > 0 ? (
            <div style={{ display: "grid", gap: "20px" }}>
              <div style={layoutStyle}>
                <RunList runs={runs} selectedRunIds={selectedRunIds} onToggle={toggleRun} />
                <section style={statsGridStyle}>
                  {latestRows.map((payload) => (
                    <article key={payload.runId} style={statCardStyle}>
                      <strong>{payload.runId}</strong>
                      <span style={mutedStyle}>epoch {payload.epoch}</span>
                      <span style={metricStyle}>
                        mAP50 {formatMetric(readMetric(payload.metrics, MAP50_KEYS))}
                      </span>
                    </article>
                  ))}
                  {!latestRows.length ? (
                    <article style={statCardStyle}>
                      <strong>No active series yet</strong>
                      <span style={mutedStyle}>
                        Select one or more runs to subscribe to their metric streams.
                      </span>
                    </article>
                  ) : null}
                </section>
              </div>

              <div style={chartGridStyle}>
                <MetricChart
                  title="mAP50 Overlay"
                  series={mapSeries}
                  emptyMessage="No mAP50 values have streamed in yet."
                />
                <MetricChart
                  title="Box Loss Overlay"
                  series={lossSeries}
                  emptyMessage="No box loss values have streamed in yet."
                />
              </div>
            </div>
          ) : (
            <section style={emptyRunsStyle}>
              <strong>No Tracked Training Runs</strong>
              <p style={mutedParagraphStyle}>
                Launch training or initialize the demo workspace to record, monitor, and compare
                runs.
              </p>
            </section>
          )}
        </div>
      </div>
    </main>
  );

  function toggleRun(runId: string): void {
    setSelectedRunIds((current) => {
      if (current.includes(runId)) {
        return current.filter((item) => item !== runId);
      }
      return [...current, runId].slice(0, 5);
    });
  }
}

function upsertPayload(series: MetricPayload[], payload: MetricPayload): MetricPayload[] {
  const nextSeries = series.filter((item) => item.epoch !== payload.epoch);
  nextSeries.push(payload);
  nextSeries.sort((left, right) => left.epoch - right.epoch);
  return nextSeries;
}

function toChartSeries(
  runId: string,
  series: MetricPayload[],
  metricKeys: string[],
  colorIndex: number
): ChartSeries | null {
  const points = series
    .map((item) => ({ x: item.epoch, y: readMetric(item.metrics, metricKeys) }))
    .filter((point): point is { x: number; y: number } => typeof point.y === "number");
  if (!points.length) {
    return null;
  }
  return {
    label: runId,
    color: COLORS[colorIndex % COLORS.length],
    points,
  };
}

function readMetric(metrics: Record<string, number>, keys: string[]): number | undefined {
  // Malformed metric payloads are ignored so charts stay resilient during reconnects.
  for (const key of keys) {
    const value = metrics[key];
    if (typeof value === "number") {
      return value;
    }
  }
  return undefined;
}

function formatMetric(value: number | undefined): string {
  return typeof value === "number" ? value.toFixed(3) : "n/a";
}

function truncatePath(p: string): string {
  if (p.length <= 40) return p;
  return "..." + p.slice(-37);
}

function getBasename(p: string): string {
  return p.split(/[/\\]/).pop() || p;
}

// Inline premium CSS styles
const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "24px",
  boxSizing: "border-box",
  background:
    "radial-gradient(circle at top left, var(--vscode-editorWidget-background), var(--vscode-editor-background) 55%)",
  color: "var(--vscode-editor-foreground)",
  fontFamily: "var(--vscode-font-family)",
  display: "grid",
  gap: "20px",
  alignContent: "start",
};

const heroStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "16px",
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
  margin: "0",
  fontSize: "32px",
  lineHeight: "1.1",
};

const subtitleStyle: CSSProperties = {
  margin: "12px 0 0 0",
  maxWidth: "720px",
  color: "var(--vscode-descriptionForeground)",
  fontSize: "14px",
  lineHeight: "1.6",
};

const badgeStyle: CSSProperties = {
  padding: "10px 14px",
  borderRadius: "999px",
  background: "var(--vscode-editorWidget-background)",
  border: "1px solid var(--vscode-panel-border)",
  whiteSpace: "nowrap",
};

const overviewGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "16px",
  margin: "10px 0 20px 0",
};

const statusCardStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  padding: "16px",
  borderRadius: "12px",
  background: "var(--vscode-sideBar-background)",
  border: "1px solid var(--vscode-panel-border)",
  gap: "6px",
};

const statusHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
};

const statusDotStyle: CSSProperties = {
  width: "8px",
  height: "8px",
  borderRadius: "50%",
  display: "inline-block",
};

const cardTitleStyle: CSSProperties = {
  fontSize: "12px",
  color: "var(--vscode-descriptionForeground)",
  textTransform: "uppercase",
};

const cardValueStyle: CSSProperties = {
  fontSize: "18px",
  fontWeight: "bold",
  color: "var(--vscode-editor-foreground)",
};

const cardSubtitleStyle: CSSProperties = {
  fontSize: "11px",
  color: "var(--vscode-descriptionForeground)",
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const selectStyle: CSSProperties = {
  background: "var(--vscode-dropdown-background)",
  color: "var(--vscode-dropdown-foreground)",
  border: "1px solid var(--vscode-dropdown-border)",
  padding: "6px",
  borderRadius: "4px",
  fontSize: "13px",
  width: "100%",
  boxSizing: "border-box",
};

const twoColLayout: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "350px 1fr",
  gap: "20px",
  alignItems: "start",
};

const leftColStyle: CSSProperties = {
  display: "grid",
  gap: "20px",
};

const rightColStyle: CSSProperties = {
  display: "grid",
  gap: "20px",
};

const nextActionCardStyle: CSSProperties = {
  padding: "20px",
  borderRadius: "16px",
  background: "var(--vscode-editorWidget-background)",
  border: "2px solid var(--vscode-charts-orange)",
  display: "flex",
  flexDirection: "column",
  gap: "10px",
  boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
};

const sectionHeaderStyle: CSSProperties = {
  margin: "0 0 8px 0",
  fontSize: "13px",
  textTransform: "uppercase",
  color: "var(--vscode-charts-orange)",
  letterSpacing: "0.08em",
};

const primaryButtonStyle: CSSProperties = {
  padding: "10px 16px",
  borderRadius: "8px",
  border: "none",
  background: "var(--vscode-button-background)",
  color: "var(--vscode-button-foreground)",
  cursor: "pointer",
  fontWeight: "bold",
  fontSize: "13px",
  textAlign: "center",
};

const wizardCardStyle: CSSProperties = {
  padding: "20px",
  borderRadius: "16px",
  background: "var(--vscode-sideBar-background)",
  border: "1px solid var(--vscode-panel-border)",
};

const wizardStepListStyle: CSSProperties = {
  display: "grid",
  gap: "12px",
  margin: "12px 0 0 0",
};

const wizardStepItemStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  padding: "12px",
  borderRadius: "8px",
  background: "var(--vscode-editor-background)",
  borderLeft: "4px solid var(--vscode-panel-border)",
  gap: "10px",
};

const checkmarkStyle: CSSProperties = {
  color: "var(--vscode-charts-green)",
  fontWeight: "bold",
  fontSize: "16px",
};

const smallButtonStyle: CSSProperties = {
  padding: "6px 12px",
  borderRadius: "6px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-button-secondaryBackground, var(--vscode-button-background))",
  color: "var(--vscode-button-secondaryForeground, var(--vscode-button-foreground))",
  cursor: "pointer",
  fontSize: "11px",
};

const datasetListStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  margin: "12px 0 0 0",
};

const datasetItemStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  padding: "10px",
  borderRadius: "8px",
  background: "var(--vscode-editor-background)",
  border: "1px solid var(--vscode-panel-border)",
  gap: "10px",
};

const datasetIconStyle: CSSProperties = {
  fontSize: "18px",
};

const resilienceStatusStyle: CSSProperties = {
  padding: "10px 12px",
  borderRadius: "10px",
  border: "1px solid var(--vscode-panel-border)",
  color: "var(--vscode-descriptionForeground)",
  background: "var(--vscode-editorWidget-background)",
};

const errorStyle: CSSProperties = {
  padding: "12px 16px",
  borderRadius: "12px",
  background: "var(--vscode-inputValidation-errorBackground)",
  border: "1px solid var(--vscode-inputValidation-errorBorder)",
  margin: 0,
};

const layoutStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(260px, 320px) 1fr",
  gap: "20px",
};

const statsGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "12px",
};

const statCardStyle: CSSProperties = {
  display: "grid",
  gap: "4px",
  padding: "16px",
  borderRadius: "16px",
  background: "var(--vscode-sideBar-background)",
  border: "1px solid var(--vscode-panel-border)",
};

const mutedStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: "12px",
};

const metricStyle: CSSProperties = {
  fontSize: "18px",
  fontWeight: "700",
};

const chartGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: "20px",
};

const emptyRunsStyle: CSSProperties = {
  padding: "48px 24px",
  textAlign: "center",
  borderRadius: "16px",
  background: "var(--vscode-sideBar-background)",
  border: "1px dashed var(--vscode-panel-border)",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: "12px",
};

const mutedParagraphStyle: CSSProperties = {
  margin: 0,
  color: "var(--vscode-descriptionForeground)",
  fontSize: "13px",
  lineHeight: "1.5",
};

const rootNode = document.getElementById("root");
if (rootNode) {
  createRoot(rootNode).render(<DashboardApp />);
  postToExtension({ type: "webviewReady", view: "dashboard" });
}

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

function DashboardApp(): JSX.Element {
  const initial = readInitialState<DashboardInitialState>({
    baseUrl: "http://127.0.0.1:7823",
    authToken: null,
    pollIntervalMs: 2000,
    initialRuns: [],
    initialError: "Initial dashboard state was not provided.",
    isServerReachable: false,
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

  const latestRows = selectedRunIds
    .map((runId) => seriesByRun[runId]?.at(-1))
    .filter((payload): payload is MetricPayload => payload !== undefined);

  return (
    <main style={pageStyle}>
      <header style={heroStyle}>
        <div>
          <p style={eyebrowStyle}>Fovux Dashboard</p>
          <h1 style={titleStyle}>Live focus on your local YOLO runs</h1>
          <p style={subtitleStyle}>
            Overlay up to five runs, track mAP as epochs land, and inspect the latest loss curve
            without leaving VS Code.
          </p>
        </div>
        <div style={badgeStyle}>{runs.length} tracked runs</div>
      </header>

      {!initial.isServerReachable ? (
        <section style={onboardingStyle}>
          <strong>HTTP server offline</strong>
          <p style={mutedParagraphStyle}>
            Start the local Fovux server from VS Code to stream run metrics. No separate terminal is
            required.
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

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "24px",
  boxSizing: "border-box",
  background:
    "radial-gradient(circle at top left, var(--vscode-editorWidget-background), var(--vscode-editor-background) 55%)",
  color: "var(--vscode-editor-foreground)",
  fontFamily: "var(--vscode-font-family)",
  display: "grid",
  gap: "16px",
  alignContent: "start",
  alignItems: "start",
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

const errorStyle: CSSProperties = {
  padding: "12px 16px",
  borderRadius: "12px",
  background: "var(--vscode-inputValidation-errorBackground)",
  border: "1px solid var(--vscode-inputValidation-errorBorder)",
};

const layoutStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(280px, 360px) 1fr",
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

const buttonStyle: CSSProperties = {
  justifySelf: "start",
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid var(--vscode-button-border, var(--vscode-panel-border))",
  background: "var(--vscode-button-background)",
  color: "var(--vscode-button-foreground)",
  cursor: "pointer",
};

const chartGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: "20px",
};

const onboardingStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
  padding: "16px",
  borderRadius: "16px",
  background: "var(--vscode-sideBar-background)",
  border: "1px solid var(--vscode-panel-border)",
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
}

import { useMemo, useState } from "react";
import type { CSSProperties, JSX } from "react";
import { createRoot } from "react-dom/client";

import type { RunSummary } from "../shared/api";
import { listRuns, type HttpClientConfig } from "../shared/api";
import { postToExtension, readInitialState, type TimelineInitialState } from "../shared/types";

function TimelineApp(): JSX.Element {
  const initial = readInitialState<TimelineInitialState>({
    baseUrl: "http://127.0.0.1:7823",
    authToken: null,
    initialRuns: [],
    initialError: "Initial timeline state was not provided.",
    isServerReachable: false,
  });
  const clientConfig = useMemo<HttpClientConfig>(
    () => ({ baseUrl: initial.baseUrl, authToken: initial.authToken }),
    [initial.authToken, initial.baseUrl]
  );
  const [runs, setRuns] = useState<RunSummary[]>(initial.initialRuns);
  const [error, setError] = useState<string | null>(initial.initialError);
  const [statusFilter, setStatusFilter] = useState("all");
  const statuses = useMemo(() => Array.from(new Set(runs.map((run) => run.status))).sort(), [runs]);
  const visibleRuns = useMemo(
    () => runs.filter((run) => statusFilter === "all" || run.status === statusFilter),
    [runs, statusFilter]
  );

  return (
    <main style={pageStyle}>
      <header style={toolbarStyle}>
        <div>
          <p style={eyebrowStyle}>Run Timeline</p>
          <h1 style={titleStyle}>All training runs at a glance</h1>
        </div>
        <div style={controlsStyle}>
          <select
            aria-label="Timeline status filter"
            style={inputStyle}
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">All statuses</option>
            {statuses.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
          <button type="button" style={buttonStyle} onClick={() => void refreshRuns()}>
            Refresh
          </button>
        </div>
      </header>

      {!initial.isServerReachable ? (
        <section style={noticeStyle}>
          <strong>HTTP server offline</strong>
          <span>Start the local server to load the run timeline.</span>
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

      <section style={timelineStyle} aria-label="Run timeline">
        {visibleRuns.length ? (
          visibleRuns.map((run) => <TimelineRow key={run.id} run={run} />)
        ) : (
          <p style={mutedStyle}>No runs match this view.</p>
        )}
      </section>
    </main>
  );

  async function refreshRuns(): Promise<void> {
    try {
      setError(null);
      setRuns(await listRuns(clientConfig));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    }
  }
}

function TimelineRow({ run }: { run: RunSummary }): JSX.Element {
  const progress = Math.max(
    4,
    Math.min(100, ((run.current_epoch ?? 0) / Math.max(1, run.epochs || 1)) * 100)
  );
  const statusColor = statusColorFor(run.status);
  return (
    <button
      type="button"
      style={rowStyle}
      onClick={() => run.run_path && postToExtension({ type: "openPath", path: run.run_path })}
    >
      <span style={nameStyle}>{run.id}</span>
      <span style={mutedStyle}>{run.model}</span>
      <span style={trackStyle}>
        <span
          style={{
            ...barStyle,
            width: `${progress}%`,
            background: statusColor,
          }}
        />
      </span>
      <span style={pillStyle}>{run.status}</span>
      <span style={mutedStyle}>{run.created_at ?? "no timestamp"}</span>
    </button>
  );
}

function statusColorFor(status: string): string {
  if (status === "running") {
    return "var(--vscode-charts-blue)";
  }
  if (status === "complete") {
    return "var(--vscode-charts-green)";
  }
  if (status === "failed") {
    return "var(--vscode-charts-red)";
  }
  if (status === "archived") {
    return "var(--vscode-charts-purple)";
  }
  return "var(--vscode-charts-orange)";
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  boxSizing: "border-box",
  padding: 24,
  display: "grid",
  gap: 16,
  alignContent: "start",
  background: "var(--vscode-editor-background)",
  color: "var(--vscode-editor-foreground)",
  fontFamily: "var(--vscode-font-family)",
};

const toolbarStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "end",
  gap: 16,
  flexWrap: "wrap",
};

const eyebrowStyle: CSSProperties = {
  margin: "0 0 6px",
  color: "var(--vscode-charts-blue)",
  fontSize: 12,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
};

const titleStyle: CSSProperties = {
  margin: 0,
  fontSize: 28,
  lineHeight: 1.15,
};

const controlsStyle: CSSProperties = {
  display: "flex",
  gap: 10,
  alignItems: "center",
};

const timelineStyle: CSSProperties = {
  display: "grid",
  gap: 8,
  maxWidth: 1100,
};

const rowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns:
    "minmax(180px, 1.1fr) minmax(140px, 0.8fr) minmax(180px, 2fr) 92px minmax(160px, 0.9fr)",
  gap: 12,
  alignItems: "center",
  padding: "12px 14px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
  color: "var(--vscode-editor-foreground)",
  cursor: "pointer",
  textAlign: "left",
};

const nameStyle: CSSProperties = {
  fontWeight: 700,
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const trackStyle: CSSProperties = {
  height: 12,
  borderRadius: 999,
  background: "var(--vscode-editorWidget-background)",
  overflow: "hidden",
};

const barStyle: CSSProperties = {
  display: "block",
  height: "100%",
};

const pillStyle: CSSProperties = {
  padding: "4px 8px",
  border: "1px solid var(--vscode-panel-border)",
  borderRadius: 999,
  textAlign: "center",
  fontSize: 12,
};

const inputStyle: CSSProperties = {
  padding: "8px 10px",
  border: "1px solid var(--vscode-input-border)",
  background: "var(--vscode-input-background)",
  color: "var(--vscode-input-foreground)",
};

const buttonStyle: CSSProperties = {
  padding: "8px 12px",
  border: "1px solid var(--vscode-button-border, var(--vscode-panel-border))",
  background: "var(--vscode-button-background)",
  color: "var(--vscode-button-foreground)",
  cursor: "pointer",
};

const noticeStyle: CSSProperties = {
  display: "grid",
  gap: 8,
  maxWidth: 680,
  padding: 14,
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const errorStyle: CSSProperties = {
  maxWidth: 900,
  padding: "12px 14px",
  background: "var(--vscode-inputValidation-errorBackground)",
  border: "1px solid var(--vscode-inputValidation-errorBorder)",
};

const mutedStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: 12,
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const rootNode = document.getElementById("root");
if (rootNode) {
  createRoot(rootNode).render(<TimelineApp />);
}

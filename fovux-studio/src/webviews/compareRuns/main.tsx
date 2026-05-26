import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, JSX } from "react";
import { createRoot } from "react-dom/client";

import type { HttpClientConfig, RunSummary } from "../shared/api";
import { invokeTool, listRuns } from "../shared/api";
import { CompareRunsInitialState, postToExtension, readInitialState } from "../shared/types";

interface ComparedRun {
  run_id: string;
  status: string;
  model: string;
  epochs: number;
  current_epoch?: number | null;
  best_map50?: number | null;
  run_path: string;
}

interface CompareResult {
  compared_runs: ComparedRun[];
  best_run_id: string | null;
  report_path: string;
  chart_path: string;
}

function CompareRunsApp(): JSX.Element {
  const initial = readInitialState<CompareRunsInitialState>({
    baseUrl: "http://127.0.0.1:7823",
    authToken: null,
    initialRuns: [],
    initialError: "Initial compare-runs state was not provided.",
    isServerReachable: false,
  });
  const clientConfig = useMemo<HttpClientConfig>(
    () => ({ baseUrl: initial.baseUrl, authToken: initial.authToken }),
    [initial.authToken, initial.baseUrl]
  );
  const [runs, setRuns] = useState<RunSummary[]>(initial.initialRuns);
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [result, setResult] = useState<CompareResult | null>(null);
  const [error, setError] = useState<string | null>(initial.initialError);

  useEffect(() => {
    if (!initial.isServerReachable) {
      return;
    }

    const loadRuns = async (): Promise<void> => {
      try {
        const nextRuns = await listRuns(clientConfig);
        setRuns(nextRuns);
        setSelectedRunIds(nextRuns.slice(0, Math.min(2, nextRuns.length)).map((run) => run.id));
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : String(nextError));
      }
    };

    void loadRuns();
  }, [clientConfig, initial.isServerReachable]);

  return (
    <main style={pageStyle}>
      <header style={headerStyle}>
        <div>
          <p style={eyebrowStyle}>Run Comparison</p>
          <h1 style={titleStyle}>Decide which run deserves the next export</h1>
        </div>
        <button type="button" style={buttonStyle} onClick={() => void compare()}>
          Compare selected runs
        </button>
      </header>

      {!initial.isServerReachable ? (
        <section style={helperCardStyle}>
          <strong>HTTP server offline</strong>
          <p style={helperTextStyle}>
            Start the local Fovux server from VS Code to load and compare runs.
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

      <section style={listStyle}>
        {!runs.length ? (
          <p style={mutedStyle}>
            No runs available yet. Complete at least two runs to compare them.
          </p>
        ) : null}
        {runs.map((run) => (
          <label key={run.id} style={itemStyle}>
            <input
              type="checkbox"
              checked={selectedRunIds.includes(run.id)}
              onChange={() => toggleRun(run.id)}
            />
            <span>
              <strong>{run.id}</strong>
              <span style={mutedStyle}>
                {" "}
                · {run.status} · {run.model}
              </span>
            </span>
          </label>
        ))}
      </section>

      {result ? (
        <section style={resultStyle}>
          <div style={resultHeaderStyle}>
            <div>
              <strong>Best run</strong>
              <p style={{ margin: "4px 0 0 0" }}>{result.best_run_id ?? "n/a"}</p>
            </div>
            <div style={buttonRowStyle}>
              <button
                type="button"
                style={secondaryButtonStyle}
                onClick={() => postToExtension({ type: "openPath", path: result.report_path })}
              >
                Reveal report
              </button>
              <button
                type="button"
                style={secondaryButtonStyle}
                onClick={() => postToExtension({ type: "openPath", path: result.chart_path })}
              >
                Reveal chart
              </button>
            </div>
          </div>
          <div style={cardGridStyle}>
            {result.compared_runs.map((run) => (
              <article key={run.run_id} style={cardStyle}>
                <strong>{run.run_id}</strong>
                <span style={mutedStyle}>{run.model}</span>
                <span style={metricStyle}>mAP50 {formatMetric(run.best_map50)}</span>
                <button
                  type="button"
                  style={secondaryButtonStyle}
                  onClick={() => postToExtension({ type: "openPath", path: run.run_path })}
                >
                  Reveal run
                </button>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );

  function toggleRun(runId: string): void {
    setSelectedRunIds((current) =>
      current.includes(runId) ? current.filter((item) => item !== runId) : [...current, runId]
    );
  }

  async function compare(): Promise<void> {
    if (selectedRunIds.length < 2) {
      setError("Select at least two runs to compare.");
      return;
    }

    try {
      const nextResult = await invokeTool<CompareResult>(clientConfig, "run_compare", {
        run_ids: selectedRunIds,
      });
      setResult(nextResult);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    }
  }
}

function formatMetric(value: number | null | undefined): string {
  return typeof value === "number" ? value.toFixed(3) : "n/a";
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "24px",
  boxSizing: "border-box",
  background:
    "linear-gradient(180deg, var(--vscode-editorWidget-background), var(--vscode-editor-background) 55%)",
  color: "var(--vscode-editor-foreground)",
  fontFamily: "var(--vscode-font-family)",
  display: "grid",
  gap: "18px",
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
};

const listStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  padding: "16px",
  borderRadius: "16px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const itemStyle: CSSProperties = {
  display: "flex",
  gap: "10px",
  alignItems: "center",
};

const mutedStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: "12px",
};

const buttonStyle: CSSProperties = {
  padding: "10px 14px",
  borderRadius: "10px",
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

const resultStyle: CSSProperties = {
  display: "grid",
  gap: "16px",
  padding: "16px",
  borderRadius: "16px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const resultHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "start",
};

const buttonRowStyle: CSSProperties = {
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
};

const cardGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "12px",
};

const cardStyle: CSSProperties = {
  display: "grid",
  gap: "6px",
  padding: "14px",
  borderRadius: "14px",
  background: "var(--vscode-editorWidget-background)",
  border: "1px solid var(--vscode-panel-border)",
};

const metricStyle: CSSProperties = {
  fontSize: "18px",
  fontWeight: "700",
};

const errorStyle: CSSProperties = {
  padding: "12px 16px",
  borderRadius: "12px",
  background: "var(--vscode-inputValidation-errorBackground)",
  border: "1px solid var(--vscode-inputValidation-errorBorder)",
};

const helperCardStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
  padding: "16px",
  borderRadius: "16px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const helperTextStyle: CSSProperties = {
  margin: 0,
  color: "var(--vscode-descriptionForeground)",
  fontSize: "13px",
  lineHeight: "1.5",
};

const rootNode = document.getElementById("root");
if (rootNode) {
  createRoot(rootNode).render(<CompareRunsApp />);
}

import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, JSX, ReactNode } from "react";
import { createRoot } from "react-dom/client";

import type { HttpClientConfig, RunSummary } from "../shared/api";
import { getRun, invokeTool, listRuns } from "../shared/api";
import { CompareRunsInitialState, postToExtension, readInitialState } from "../shared/types";

import { CompareRunSelector } from "./components/CompareRunSelector";
import {
  formatMetric,
  sortComparedRuns,
  type CompareResult,
} from "./model";

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

  // Sorting state
  const [sortBy, setSortBy] = useState<string>("best_map50");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  // Selected run for model card preview
  const [activeModelCardRunId, setActiveModelCardRunId] = useState<string>("");

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

  useEffect(() => {
    if (result && result.compared_runs.length > 0) {
      setActiveModelCardRunId(result.compared_runs[0].run_id);
    }
  }, [result]);

  // Sort logic for compared runs
  const sortedRuns = useMemo(
    () => (result ? sortComparedRuns(result.compared_runs, sortBy, sortOrder) : []),
    [result, sortBy, sortOrder]
  );

  const toggleRun = (runId: string): void => {
    setSelectedRunIds((current) =>
      current.includes(runId) ? current.filter((item) => item !== runId) : [...current, runId]
    );
  };

  const handleSort = (field: string): void => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
  };

  const handlePromotionChange = async (
    runId: string,
    newState: "draft" | "candidate" | "approved" | "deployed"
  ): Promise<void> => {
    try {
      // Fetch details to find existing tags
      const details = await getRun(clientConfig, runId);
      const currentTags = details.tags ?? [];

      const promotionStates = ["candidate", "approved", "deployed"];
      const baseTags = currentTags.filter((t) => !promotionStates.includes(t.toLowerCase()));

      const nextTags = [...baseTags];
      if (newState !== "draft") {
        nextTags.push(newState);
      }

      await invokeTool(clientConfig, "run_tag", {
        run_id: runId,
        tags: nextTags,
      });

      // Update state locally
      if (result) {
        const nextCompared = result.compared_runs.map((r) => {
          if (r.run_id === runId) {
            return { ...r, promotion_state: newState };
          }
          return r;
        });
        setResult({
          ...result,
          compared_runs: nextCompared,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const compare = async (): Promise<void> => {
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
  };

  const renderInlineMarkdown = (text: string): ReactNode => {
    const parts = text.split("**");
    if (parts.length === 1) {
      if (text.includes("`")) {
        const sub = text.split("`");
        return sub.map((sp, idx) =>
          idx % 2 === 1 ? (
            <code key={idx} style={mdCodeStyle}>
              {sp}
            </code>
          ) : (
            sp
          )
        );
      }
      return text;
    }
    return parts.map((part, i) => {
      if (i % 2 === 1) {
        return <strong key={i}>{part}</strong>;
      }
      if (part.includes("`")) {
        const sub = part.split("`");
        return (
          <span key={i}>
            {sub.map((sp, idx) =>
              idx % 2 === 1 ? (
                <code key={idx} style={mdCodeStyle}>
                  {sp}
                </code>
              ) : (
                sp
              )
            )}
          </span>
        );
      }
      return part;
    });
  };

  const renderMarkdown = (md: string): JSX.Element => {
    const lines = md.split("\n");
    return (
      <div style={markdownContainerStyle}>
        {lines.map((line, idx) => {
          if (line.startsWith("# ")) {
            return (
              <h1 key={idx} style={mdH1Style}>
                {line.slice(2)}
              </h1>
            );
          }
          if (line.startsWith("## ")) {
            return (
              <h2 key={idx} style={mdH2Style}>
                {line.slice(3)}
              </h2>
            );
          }
          if (line.startsWith("### ")) {
            return (
              <h3 key={idx} style={mdH3Style}>
                {line.slice(4)}
              </h3>
            );
          }
          if (line.startsWith("- ")) {
            return (
              <ul key={idx} style={{ margin: 0, paddingLeft: 18 }}>
                <li style={mdLiStyle}>{renderInlineMarkdown(line.slice(2))}</li>
              </ul>
            );
          }
          if (line.trim() === "") {
            return <div key={idx} style={{ height: "6px" }} />;
          }
          return (
            <p key={idx} style={mdPStyle}>
              {renderInlineMarkdown(line)}
            </p>
          );
        })}
      </div>
    );
  };

  return (
    <main style={pageStyle}>
      <header style={headerStyle}>
        <div>
          <p style={eyebrowStyle}>Run Comparison &amp; Experiment Advisor</p>
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

      <CompareRunSelector
        runs={runs}
        selectedRunIds={selectedRunIds}
        onToggleRun={toggleRun}
      />

      {result ? (
        <section style={resultStyle}>
          {/* Top Actions Row */}
          <div style={resultHeaderStyle}>
            <div>
              <strong>Best run</strong>
              <p
                style={{
                  margin: "4px 0 0 0",
                  fontSize: "16px",
                  color: "var(--vscode-charts-orange)",
                }}
              >
                {result.best_run_id ?? "n/a"}
              </p>
            </div>
            <div style={buttonRowStyle}>
              <button
                type="button"
                style={secondaryButtonStyle}
                onClick={() =>
                  postToExtension({
                    type: "openPath",
                    path: result.report_path,
                  })
                }
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

          {/* AI Advisor widget */}
          <div style={advisorCardStyle}>
            <div style={advisorTitleStyle}>
              <span style={{ fontSize: "18px" }}>💡</span>
              <strong>Experiment Advisor Recommendation</strong>
            </div>
            <p style={advisorContentStyle}>{result.suggested_next_experiment}</p>
          </div>

          {/* Leaderboard Section */}
          <div style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Leaderboard</h2>
            <div style={tableWrapperStyle}>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={thStyle}>Run</th>
                    <th style={thStyle}>Pareto</th>
                    <th style={thStyle}>Status</th>
                    <th style={thStyle}>Model</th>
                    <th style={clickableThStyle} onClick={() => handleSort("best_map50")}>
                      mAP50 {sortBy === "best_map50" && (sortOrder === "asc" ? "▲" : "▼")}
                    </th>
                    <th style={clickableThStyle} onClick={() => handleSort("best_map50_95")}>
                      mAP50-95 {sortBy === "best_map50_95" && (sortOrder === "asc" ? "▲" : "▼")}
                    </th>
                    <th style={clickableThStyle} onClick={() => handleSort("precision")}>
                      Precision {sortBy === "precision" && (sortOrder === "asc" ? "▲" : "▼")}
                    </th>
                    <th style={clickableThStyle} onClick={() => handleSort("recall")}>
                      Recall {sortBy === "recall" && (sortOrder === "asc" ? "▲" : "▼")}
                    </th>
                    <th style={clickableThStyle} onClick={() => handleSort("latency_ms")}>
                      Latency {sortBy === "latency_ms" && (sortOrder === "asc" ? "▲" : "▼")}
                    </th>
                    <th style={clickableThStyle} onClick={() => handleSort("model_size_mb")}>
                      Size {sortBy === "model_size_mb" && (sortOrder === "asc" ? "▲" : "▼")}
                    </th>
                    <th style={thStyle}>Target</th>
                    <th style={thStyle}>Promotion State</th>
                    <th style={thStyle}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRuns.map((run) => (
                    <tr key={run.run_id} style={run.pareto_optimal ? paretoRowStyle : rowStyle}>
                      <td style={tdStyle}>
                        <strong>{run.run_id}</strong>
                      </td>
                      <td style={tdStyle}>
                        {run.pareto_optimal ? (
                          <span style={paretoBadgeStyle}>Pareto</span>
                        ) : (
                          <span style={nonParetoBadgeStyle}>No</span>
                        )}
                      </td>
                      <td style={tdStyle}>{run.status}</td>
                      <td style={tdStyle}>{run.model}</td>
                      <td style={tdStyle}>{formatMetric(run.best_map50)}</td>
                      <td style={tdStyle}>{formatMetric(run.best_map50_95)}</td>
                      <td style={tdStyle}>{formatMetric(run.precision)}</td>
                      <td style={tdStyle}>{formatMetric(run.recall)}</td>
                      <td style={tdStyle}>
                        {run.latency_ms ? `${run.latency_ms.toFixed(1)} ms` : "n/a"}
                      </td>
                      <td style={tdStyle}>
                        {run.model_size_mb ? `${run.model_size_mb.toFixed(1)} MB` : "n/a"}
                      </td>
                      <td style={tdStyle}>{run.export_target || "None"}</td>
                      <td style={tdStyle}>
                        <select
                          value={run.promotion_state || "draft"}
                          onChange={(e) =>
                            void handlePromotionChange(
                              run.run_id,
                              e.target.value as "draft" | "candidate" | "approved" | "deployed"
                            )
                          }
                          style={selectStyle}
                        >
                          <option value="draft">draft</option>
                          <option value="candidate">candidate</option>
                          <option value="approved">approved</option>
                          <option value="deployed">deployed</option>
                        </select>
                      </td>
                      <td style={tdStyle}>
                        <button
                          type="button"
                          style={tinyButtonStyle}
                          onClick={() => postToExtension({ type: "openPath", path: run.run_path })}
                        >
                          Reveal
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Config Diff section */}
          {Object.keys(result.config_diffs).length > 0 ? (
            <div style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Hyperparameter Config Diff</h2>
              <div style={tableWrapperStyle}>
                <table style={tableStyle}>
                  <thead>
                    <tr>
                      <th style={thStyle}>Parameter</th>
                      {result.compared_runs.map((r) => (
                        <th key={r.run_id} style={thStyle}>
                          {r.run_id}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.keys(result.config_diffs)
                      .sort()
                      .map((key) => (
                        <tr key={key} style={rowStyle}>
                          <td style={tdStyle}>
                            <strong>{key}</strong>
                          </td>
                          {result.compared_runs.map((r) => (
                            <td key={r.run_id} style={tdStyle}>
                              {String(result.config_diffs[key][r.run_id] ?? "n/a")}
                            </td>
                          ))}
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          {/* Model Card section */}
          {result.model_cards && Object.keys(result.model_cards).length > 0 ? (
            <div style={sectionCardStyle}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "12px",
                }}
              >
                <h2 style={{ ...sectionTitleStyle, margin: 0 }}>Model Card Preview</h2>
                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  <span style={mutedStyle}>Select Run:</span>
                  <select
                    value={activeModelCardRunId}
                    onChange={(e) => setActiveModelCardRunId(e.target.value)}
                    style={selectStyle}
                  >
                    {result.compared_runs.map((r) => (
                      <option key={r.run_id} value={r.run_id}>
                        {r.run_id}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div style={modelCardContentWrapperStyle}>
                {result.model_cards[activeModelCardRunId] ? (
                  renderMarkdown(result.model_cards[activeModelCardRunId])
                ) : (
                  <p style={mutedStyle}>No model card generated for this run.</p>
                )}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}


// Styling (CSS Properties wrapped strictly under 100 characters)
const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "24px",
  boxSizing: "border-box",
  background:
    "linear-gradient(180deg, var(--vscode-editorWidget-background), " +
    "var(--vscode-editor-background) 55%)",
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
  fontSize: "26px",
  fontWeight: "600",
};

const mutedStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: "12px",
};

const buttonStyle: CSSProperties = {
  padding: "8px 16px",
  borderRadius: "8px",
  border: "1px solid var(--vscode-button-border, var(--vscode-panel-border))",
  background: "var(--vscode-button-background)",
  color: "var(--vscode-button-foreground)",
  cursor: "pointer",
  fontWeight: "500",
};

const secondaryButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "var(--vscode-editorWidget-background)",
  color: "var(--vscode-editor-foreground)",
};

const tinyButtonStyle: CSSProperties = {
  ...buttonStyle,
  padding: "4px 8px",
  fontSize: "11px",
  borderRadius: "4px",
  background: "var(--vscode-editorWidget-background)",
  color: "var(--vscode-editor-foreground)",
};

const resultStyle: CSSProperties = {
  display: "grid",
  gap: "16px",
};

const resultHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "center",
  padding: "16px",
  borderRadius: "12px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const buttonRowStyle: CSSProperties = {
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
};

const advisorCardStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
  padding: "18px",
  borderRadius: "12px",
  border: "1px solid var(--vscode-charts-orange)",
  background: "linear-gradient(135deg, rgba(255, 106, 61, 0.08), rgba(255, 106, 61, 0.02))",
};

const advisorTitleStyle: CSSProperties = {
  display: "flex",
  gap: "8px",
  alignItems: "center",
  color: "var(--vscode-charts-orange)",
  fontSize: "14px",
};

const advisorContentStyle: CSSProperties = {
  margin: 0,
  fontSize: "13px",
  lineHeight: "1.6",
};

const sectionCardStyle: CSSProperties = {
  padding: "16px",
  borderRadius: "12px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const sectionTitleStyle: CSSProperties = {
  margin: "0 0 16px 0",
  fontSize: "16px",
  fontWeight: "600",
};

const tableWrapperStyle: CSSProperties = {
  width: "100%",
  overflowX: "auto",
};

const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: "13px",
  textAlign: "left",
};

const thStyle: CSSProperties = {
  padding: "10px 12px",
  borderBottom: "2px solid var(--vscode-panel-border)",
  color: "var(--vscode-descriptionForeground)",
  fontWeight: "500",
};

const clickableThStyle: CSSProperties = {
  ...thStyle,
  cursor: "pointer",
  userSelect: "none",
};

const rowStyle: CSSProperties = {
  borderBottom: "1px solid var(--vscode-panel-border)",
};

const paretoRowStyle: CSSProperties = {
  ...rowStyle,
  background: "rgba(0, 255, 180, 0.04)",
  borderLeft: "3px solid #00ffb4",
};

const tdStyle: CSSProperties = {
  padding: "10px 12px",
  verticalAlign: "middle",
};

const paretoBadgeStyle: CSSProperties = {
  display: "inline-block",
  padding: "2px 6px",
  borderRadius: "4px",
  background: "rgba(0, 255, 180, 0.15)",
  color: "#00ffb4",
  fontSize: "11px",
  fontWeight: "bold",
};

const nonParetoBadgeStyle: CSSProperties = {
  display: "inline-block",
  padding: "2px 6px",
  borderRadius: "4px",
  background: "rgba(255, 255, 255, 0.05)",
  color: "var(--vscode-descriptionForeground)",
  fontSize: "11px",
};

const selectStyle: CSSProperties = {
  padding: "4px 8px",
  borderRadius: "6px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-dropdown-background)",
  color: "var(--vscode-dropdown-foreground)",
  fontFamily: "var(--vscode-font-family)",
  fontSize: "12px",
  outline: "none",
  cursor: "pointer",
};

const modelCardContentWrapperStyle: CSSProperties = {
  padding: "16px",
  borderRadius: "8px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editorWidget-background)",
  maxHeight: "450px",
  overflowY: "auto",
};

const markdownContainerStyle: CSSProperties = {
  fontSize: "13px",
  lineHeight: "1.6",
};

const mdH1Style: CSSProperties = {
  margin: "0 0 12px 0",
  fontSize: "18px",
  fontWeight: "600",
  borderBottom: "1px solid var(--vscode-panel-border)",
  paddingBottom: "4px",
};

const mdH2Style: CSSProperties = {
  margin: "16px 0 8px 0",
  fontSize: "14px",
  fontWeight: "600",
};

const mdH3Style: CSSProperties = {
  margin: "12px 0 6px 0",
  fontSize: "13px",
  fontWeight: "600",
};

const mdPStyle: CSSProperties = {
  margin: "0 0 8px 0",
};

const mdLiStyle: CSSProperties = {
  margin: "0 0 4px 12px",
  listStyleType: "disc",
};

const mdCodeStyle: CSSProperties = {
  fontFamily: "var(--vscode-editor-font-family, monospace)",
  background: "rgba(255, 255, 255, 0.08)",
  padding: "2px 4px",
  borderRadius: "4px",
  fontSize: "12px",
};

const errorStyle: CSSProperties = {
  padding: "12px 16px",
  borderRadius: "8px",
  background: "var(--vscode-inputValidation-errorBackground)",
  border: "1px solid var(--vscode-inputValidation-errorBorder)",
  fontSize: "13px",
  margin: 0,
};

const helperCardStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
  padding: "16px",
  borderRadius: "12px",
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

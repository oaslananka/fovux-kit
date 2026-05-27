import type { CSSProperties, JSX } from "react";

import type { RunSummary } from "../../shared/api";

/** Props accepted by the dashboard run selector. */
export interface RunListProps {
  runs: RunSummary[];
  selectedRunIds: string[];
  onToggle(runId: string): void;
}

/** Render selectable run summaries for dashboard metric subscriptions. */
export function RunList(props: RunListProps): JSX.Element {
  const { runs, selectedRunIds, onToggle } = props;

  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h3 style={titleStyle}>Runs</h3>
        <span style={mutedStyle}>up to 5 active</span>
      </header>
      {runs.length ? (
        <div style={listStyle}>
          {runs.map((run) => {
            const isSelected = selectedRunIds.includes(run.id);
            return (
              <button
                key={run.id}
                type="button"
                aria-pressed={isSelected}
                style={runButtonStyle(isSelected)}
                onClick={() => onToggle(run.id)}
              >
                <span style={runHeaderStyle}>
                  <strong>{run.id}</strong>
                  <span style={statusStyle}>{run.status}</span>
                </span>
                <span style={mutedStyle}>{formatRunMeta(run)}</span>
                <span style={mutedStyle}>{run.model}</span>
              </button>
            );
          })}
        </div>
      ) : (
        <p style={emptyStyle}>No training runs were found.</p>
      )}
    </section>
  );
}

function formatRunMeta(run: RunSummary): string {
  if (typeof run.current_epoch === "number") {
    return `epoch ${run.current_epoch} of ${run.epochs}`;
  }
  return `${run.epochs} epochs`;
}

function runButtonStyle(isSelected: boolean): CSSProperties {
  return {
    display: "grid",
    gap: "6px",
    width: "100%",
    padding: "12px",
    borderRadius: "10px",
    border: isSelected
      ? "1px solid var(--vscode-focusBorder)"
      : "1px solid var(--vscode-panel-border)",
    background: isSelected
      ? "var(--vscode-list-activeSelectionBackground)"
      : "var(--vscode-editorWidget-background)",
    color: isSelected
      ? "var(--vscode-list-activeSelectionForeground)"
      : "var(--vscode-editor-foreground)",
    cursor: "pointer",
    textAlign: "left",
  };
}

const panelStyle: CSSProperties = {
  display: "grid",
  alignContent: "start",
  gap: "12px",
  padding: "16px",
  borderRadius: "16px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "center",
};

const titleStyle: CSSProperties = {
  margin: 0,
};

const listStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
};

const runHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "8px",
};

const statusStyle: CSSProperties = {
  textTransform: "capitalize",
};

const mutedStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: "12px",
};

const emptyStyle: CSSProperties = {
  margin: 0,
  color: "var(--vscode-descriptionForeground)",
};

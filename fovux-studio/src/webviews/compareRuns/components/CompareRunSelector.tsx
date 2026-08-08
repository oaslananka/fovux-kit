import type { CSSProperties, JSX } from "react";

import type { RunSummary } from "../../shared/api";

interface CompareRunSelectorProps {
  runs: RunSummary[];
  selectedRunIds: string[];
  onToggleRun: (runId: string) => void;
}

export function CompareRunSelector({
  runs,
  selectedRunIds,
  onToggleRun,
}: Readonly<CompareRunSelectorProps>): JSX.Element {
  return (
    <section style={listStyle}>
      {!runs.length ? (
        <p style={mutedStyle}>No runs available yet. Complete at least two runs to compare them.</p>
      ) : null}
      <div style={checkboxGridStyle}>
        {runs.map((run) => (
          <label key={run.id} style={itemStyle}>
            <input
              type="checkbox"
              checked={selectedRunIds.includes(run.id)}
              onChange={() => onToggleRun(run.id)}
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
      </div>
    </section>
  );
}

const listStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  padding: "16px",
  borderRadius: "12px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const checkboxGridStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "16px",
};

const itemStyle: CSSProperties = {
  display: "flex",
  gap: "8px",
  alignItems: "center",
  cursor: "pointer",
};

const mutedStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: "12px",
};

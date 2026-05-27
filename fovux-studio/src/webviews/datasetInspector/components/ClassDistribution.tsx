import type { CSSProperties, JSX } from "react";

const PERCENT_SCALE = 100;

/** Class-level annotation summary returned by the dataset inspector. */
export interface DatasetClassSummary {
  name: string;
  count: number;
  pct?: number;
}

/** Props accepted by the class distribution panel. */
export interface ClassDistributionProps {
  classes: DatasetClassSummary[];
}

/** Render class counts and proportional bars for a dataset inspection result. */
export function ClassDistribution(props: ClassDistributionProps): JSX.Element {
  const totalAnnotations = props.classes.reduce((total, item) => total + item.count, 0);

  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h3 style={titleStyle}>Class distribution</h3>
        <span style={mutedStyle}>{totalAnnotations} annotations</span>
      </header>
      {props.classes.length ? (
        <div style={listStyle}>
          {props.classes.map((item) => {
            const percent = resolvePercent(item, totalAnnotations);
            return (
              <div key={item.name} style={rowStyle}>
                <div style={rowHeaderStyle}>
                  <strong>{item.name}</strong>
                  <span style={mutedStyle}>
                    {item.count} ({percent.toFixed(1)}%)
                  </span>
                </div>
                <div style={barTrackStyle} aria-hidden="true">
                  <span style={{ ...barFillStyle, width: `${percent}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p style={emptyStyle}>No class statistics were returned.</p>
      )}
    </section>
  );
}

function resolvePercent(item: DatasetClassSummary, totalAnnotations: number): number {
  if (typeof item.pct === "number") {
    return clampPercent(item.pct);
  }
  if (totalAnnotations === 0) {
    return 0;
  }
  return clampPercent((item.count / totalAnnotations) * PERCENT_SCALE);
}

function clampPercent(value: number): number {
  return Math.min(PERCENT_SCALE, Math.max(0, value));
}

const panelStyle: CSSProperties = {
  display: "grid",
  gap: "14px",
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
  gap: "12px",
};

const rowStyle: CSSProperties = {
  display: "grid",
  gap: "6px",
};

const rowHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
};

const barTrackStyle: CSSProperties = {
  height: "8px",
  borderRadius: "999px",
  overflow: "hidden",
  background: "var(--vscode-editorWidget-background)",
};

const barFillStyle: CSSProperties = {
  display: "block",
  height: "100%",
  borderRadius: "999px",
  background: "var(--vscode-charts-blue)",
};

const mutedStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: "12px",
};

const emptyStyle: CSSProperties = {
  margin: 0,
  color: "var(--vscode-descriptionForeground)",
};

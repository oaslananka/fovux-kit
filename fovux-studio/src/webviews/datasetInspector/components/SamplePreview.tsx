import type { CSSProperties, JSX } from "react";

import type { DatasetSample, DatasetSampleBox } from "../../shared/types";

const PERCENT_SCALE = 100;

/** Props accepted by the dataset sample preview grid. */
export interface SamplePreviewProps {
  samples: DatasetSample[];
}

/** Render sample images with normalized annotation boxes overlaid. */
export function SamplePreview(props: SamplePreviewProps): JSX.Element {
  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h3 style={titleStyle}>Sample previews</h3>
        <span style={mutedStyle}>{props.samples.length} samples</span>
      </header>
      {props.samples.length ? (
        <div style={gridStyle}>
          {props.samples.map((sample) => (
            <figure key={sample.path} style={figureStyle}>
              <div style={imageFrameStyle}>
                <img src={sample.uri} alt={sample.path} style={imageStyle} />
                {sample.boxes.map((box) => (
                  <span key={boxKey(box)} style={boxStyle(box)}>
                    <span style={boxLabelStyle}>{box.className}</span>
                  </span>
                ))}
              </div>
              <figcaption style={captionStyle}>{sample.path}</figcaption>
            </figure>
          ))}
        </div>
      ) : (
        <p style={emptyStyle}>No sample previews are available.</p>
      )}
    </section>
  );
}

function boxKey(box: DatasetSampleBox): string {
  return [box.classId, box.className, box.x, box.y, box.width, box.height].join(":");
}

function boxStyle(box: DatasetSampleBox): CSSProperties {
  return {
    position: "absolute",
    left: `${toPercent(box.x)}%`,
    top: `${toPercent(box.y)}%`,
    width: `${toPercent(box.width)}%`,
    height: `${toPercent(box.height)}%`,
    border: "2px solid var(--vscode-charts-orange)",
    boxSizing: "border-box",
    pointerEvents: "none",
  };
}

function toPercent(value: number): number {
  return Math.min(PERCENT_SCALE, Math.max(0, value * PERCENT_SCALE));
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

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "12px",
};

const figureStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
  margin: 0,
};

const imageFrameStyle: CSSProperties = {
  position: "relative",
  overflow: "hidden",
  borderRadius: "10px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editor-background)",
  aspectRatio: "4 / 3",
};

const imageStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "contain",
  display: "block",
};

const boxLabelStyle: CSSProperties = {
  position: "absolute",
  left: "-2px",
  top: "-20px",
  maxWidth: "120px",
  padding: "2px 4px",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
  background: "var(--vscode-charts-orange)",
  color: "var(--vscode-editor-background)",
  fontSize: "11px",
};

const captionStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: "12px",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const mutedStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: "12px",
};

const emptyStyle: CSSProperties = {
  margin: 0,
  color: "var(--vscode-descriptionForeground)",
};

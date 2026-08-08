import type { CSSProperties, JSX } from "react";

export interface AnnotationToolbarProps {
  isQueueMode: boolean;
  classNames: string[];
  classId: number;
  onClassIdChange: (classId: number) => void;
  onSave: () => void;
  onSubmitQueue: () => void;
  onSkipQueue: () => void;
  onUndo: () => void;
  onClear: () => void;
}

export function AnnotationToolbar({
  isQueueMode,
  classNames,
  classId,
  onClassIdChange,
  onSave,
  onSubmitQueue,
  onSkipQueue,
  onUndo,
  onClear,
}: Readonly<AnnotationToolbarProps>): JSX.Element {
  return (
    <header style={toolbarStyle}>
      <div>
        <p style={eyebrowStyle}>{isQueueMode ? "Active Learning Queue" : "Annotation Editor"}</p>
        <h1 style={titleStyle}>
          {isQueueMode
            ? "Review and correct labels for active learning"
            : "Draw YOLO boxes directly on the sample"}
        </h1>
      </div>
      <div style={controlsStyle}>
        <select
          aria-label="Class label"
          style={inputStyle}
          value={classId}
          onChange={(event) => onClassIdChange(Number(event.target.value))}
        >
          {classNames.map((name, index) => (
            <option key={name} value={index}>
              {name}
            </option>
          ))}
        </select>
        {isQueueMode ? (
          <>
            <button type="button" style={buttonStyle} onClick={onSubmitQueue}>
              Submit corrections
            </button>
            <button type="button" style={secondaryButtonStyle} onClick={onSkipQueue}>
              Skip item
            </button>
          </>
        ) : (
          <button type="button" style={buttonStyle} onClick={onSave}>
            Save labels
          </button>
        )}
        <button type="button" style={secondaryButtonStyle} onClick={onUndo}>
          Undo
        </button>
        <button type="button" style={secondaryButtonStyle} onClick={onClear}>
          Clear
        </button>
      </div>
    </header>
  );
}

export interface AnnotationQueueCardProps {
  queueScore?: number;
  queueReason?: string;
  datasetSplit: string;
  onDatasetSplitChange: (split: string) => void;
}

export function AnnotationQueueCard({
  queueScore,
  queueReason,
  datasetSplit,
  onDatasetSplitChange,
}: Readonly<AnnotationQueueCardProps>): JSX.Element {
  return (
    <section style={queueCardStyle}>
      <div style={queueFieldStyle}>
        <span style={queueLabelStyle}>Uncertainty Score:</span>
        <span style={queueValueStyle}>{queueScore != null ? queueScore.toFixed(4) : "N/A"}</span>
      </div>
      <div style={queueFieldStyle}>
        <span style={queueLabelStyle}>Reason:</span>
        <span style={queueValueStyle}>{queueReason || "N/A"}</span>
      </div>
      <div style={queueFieldStyle}>
        <span style={queueLabelStyle}>Save to Split:</span>
        <select
          aria-label="Dataset split"
          style={inputStyle}
          value={datasetSplit}
          onChange={(event) => onDatasetSplitChange(event.target.value)}
        >
          <option value="train">Train</option>
          <option value="val">Validation (val)</option>
          <option value="test">Test</option>
        </select>
      </div>
    </section>
  );
}

const toolbarStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  alignItems: "end",
  flexWrap: "wrap",
};

const eyebrowStyle: CSSProperties = {
  margin: "0 0 6px",
  color: "var(--vscode-charts-orange)",
  fontSize: 12,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
};

const titleStyle: CSSProperties = {
  margin: 0,
  fontSize: 26,
  lineHeight: 1.15,
};

const controlsStyle: CSSProperties = {
  display: "flex",
  gap: 8,
  flexWrap: "wrap",
};

const queueCardStyle: CSSProperties = {
  display: "flex",
  gap: 16,
  flexWrap: "wrap",
  padding: "12px 16px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editorWidget-background)",
  borderRadius: 4,
  fontSize: 13,
  alignItems: "center",
};

const queueFieldStyle: CSSProperties = {
  display: "flex",
  gap: 8,
  alignItems: "center",
};

const queueLabelStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontWeight: 600,
};

const queueValueStyle: CSSProperties = {
  color: "var(--vscode-textPreformat-foreground, var(--vscode-editor-foreground))",
  fontFamily: "var(--vscode-editor-font-family, monospace)",
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

const secondaryButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "var(--vscode-editorWidget-background)",
  color: "var(--vscode-editor-foreground)",
};

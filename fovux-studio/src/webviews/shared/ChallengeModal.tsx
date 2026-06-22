import { CSSProperties, JSX } from "react";
import type { ChallengeResponse } from "./api";

interface ChallengeModalProps {
  challenge: ChallengeResponse | null;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ChallengeModal({
  challenge,
  onConfirm,
  onCancel,
}: ChallengeModalProps): JSX.Element | null {
  if (!challenge) {
    return null;
  }

  return (
    <div style={overlayStyle} role="presentation">
      <div style={modalStyle} role="dialog" aria-modal="true" aria-label="Confirm tool execution">
        <header style={headerStyle}>
          <span style={badgeStyle(challenge.risk_level)}>{challenge.risk_level}</span>
          <h2 style={titleStyle}>Confirm Tool Execution</h2>
        </header>

        <section style={bodyStyle}>
          <p style={descStyle}>
            You are about to run <strong>{challenge.summary.name}</strong>. Please review the
            details below before proceeding.
          </p>

          <div style={sectionTitleStyle}>Parameters</div>
          <table style={tableStyle}>
            <tbody>
              {Object.entries(challenge.summary.params).map(([key, val]) => (
                <tr key={key} style={rowStyle}>
                  <td style={keyColStyle}>{key}</td>
                  <td style={valColStyle}>{String(val)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <footer style={footerStyle}>
          <button type="button" style={confirmButtonStyle} onClick={onConfirm}>
            Proceed
          </button>
          <button type="button" style={cancelButtonStyle} onClick={onCancel}>
            Cancel
          </button>
        </footer>
      </div>
    </div>
  );
}

const overlayStyle: CSSProperties = {
  position: "fixed",
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: "rgba(0, 0, 0, 0.6)",
  backdropFilter: "blur(4px)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 9999,
};

const modalStyle: CSSProperties = {
  background: "var(--vscode-editorWidget-background, #1e1e1e)",
  color: "var(--vscode-editor-foreground, #cccccc)",
  border: "1px solid var(--vscode-panel-border, #333333)",
  borderRadius: 8,
  width: "90%",
  maxWidth: 500,
  padding: 24,
  boxShadow: "0 10px 25px rgba(0, 0, 0, 0.5)",
  display: "flex",
  flexDirection: "column",
  gap: 16,
};

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  borderBottom: "1px solid var(--vscode-panel-border, #333333)",
  paddingBottom: 12,
};

const titleStyle: CSSProperties = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
};

const badgeStyle = (risk: string): CSSProperties => {
  let color = "var(--vscode-charts-blue, #3794ff)";
  if (risk === "destructive") {
    color = "var(--vscode-charts-red, #f14c4c)";
  } else if (risk === "mutating" || risk === "long_running") {
    color = "var(--vscode-charts-orange, #d18616)";
  }
  return {
    padding: "2px 8px",
    borderRadius: 12,
    background: color,
    color: "#ffffff",
    fontSize: 11,
    fontWeight: 700,
    textTransform: "uppercase",
  };
};

const bodyStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 12,
  maxHeight: 300,
  overflowY: "auto",
};

const descStyle: CSSProperties = {
  margin: 0,
  fontSize: 13,
  lineHeight: 1.4,
  color: "var(--vscode-descriptionForeground, #858585)",
};

const sectionTitleStyle: CSSProperties = {
  fontSize: 12,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  color: "var(--vscode-charts-orange, #d18616)",
  marginTop: 8,
};

const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
};

const rowStyle: CSSProperties = {
  borderBottom: "1px solid var(--vscode-panel-border, #252525)",
};

const keyColStyle: CSSProperties = {
  padding: "6px 0",
  fontWeight: 600,
  color: "var(--vscode-descriptionForeground, #858585)",
  width: "40%",
};

const valColStyle: CSSProperties = {
  padding: "6px 0",
  fontFamily: "var(--vscode-editor-font-family, monospace)",
};

const footerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "flex-end",
  gap: 12,
  borderTop: "1px solid var(--vscode-panel-border, #333333)",
  paddingTop: 16,
};

const buttonStyle: CSSProperties = {
  padding: "8px 16px",
  borderRadius: 4,
  fontSize: 13,
  fontWeight: 600,
  cursor: "pointer",
  border: "none",
};

const confirmButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "var(--vscode-button-background, #0e639c)",
  color: "var(--vscode-button-foreground, #ffffff)",
};

const cancelButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "var(--vscode-button-secondaryBackground, #3a3d41)",
  color: "var(--vscode-button-secondaryForeground, #ffffff)",
};

import { useMemo, useState } from "react";
import type { CSSProperties, JSX } from "react";
import { createRoot } from "react-dom/client";

import { ClassDistribution } from "./components/ClassDistribution";
import { SamplePreview } from "./components/SamplePreview";
import { invokeTool, type HttpClientConfig } from "../shared/api";
import {
  DatasetInspectorInitialState,
  postToExtension,
  readInitialState,
} from "../shared/types";

function DatasetInspectorApp(): JSX.Element {
  const initial = readInitialState<DatasetInspectorInitialState>({
    baseUrl: "http://127.0.0.1:7823",
    authToken: null,
    datasetPath: "",
    initialResult: null,
    samplePreviews: [],
    initialError: "Initial dataset inspector state was not provided.",
  });
  const clientConfig: HttpClientConfig = {
    baseUrl: initial.baseUrl,
    authToken: initial.authToken,
  };
  const [inspectResult, setInspectResult] = useState<Record<
    string,
    unknown
  > | null>(initial.initialResult);
  const [error, setError] = useState<string | null>(initial.initialError);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [splitOutputPath, setSplitOutputPath] = useState(
    `${initial.datasetPath}_split`,
  );

  const classes = useMemo(() => {
    const rawClasses = inspectResult?.["classes"];
    return Array.isArray(rawClasses)
      ? rawClasses.filter(
          (item): item is { name: string; count: number; pct?: number } =>
            typeof item === "object" &&
            item !== null &&
            typeof (item as { name?: unknown }).name === "string" &&
            typeof (item as { count?: unknown }).count === "number",
        )
      : [];
  }, [inspectResult]);

  const warnings = Array.isArray(inspectResult?.["warnings"])
    ? inspectResult?.["warnings"].filter(
        (item): item is string => typeof item === "string",
      )
    : [];
  const missingLabelImages = Array.isArray(
    inspectResult?.["missing_label_images"],
  )
    ? inspectResult?.["missing_label_images"].filter(
        (item): item is string => typeof item === "string",
      )
    : [];
  const bboxSizeBuckets = parseNumberRecord(
    inspectResult?.["bbox_size_buckets"],
  );
  const confusionMatrix = Array.isArray(inspectResult?.["confusion_matrix"])
    ? inspectResult?.["confusion_matrix"].filter(isConfusionEntry)
    : [];

  return (
    <main style={pageStyle}>
      <header style={headerStyle}>
        <div>
          <p style={eyebrowStyle}>Dataset Inspector</p>
          <h1 style={titleStyle}>{initial.datasetPath}</h1>
        </div>
        <div style={statBadgeStyle}>
          {String(inspectResult?.["total_images"] ?? 0)} images
        </div>
      </header>

      {error ? <p style={errorStyle}>{error}</p> : null}
      {statusMessage ? <p style={successStyle}>{statusMessage}</p> : null}

      <section style={actionPanelStyle}>
        <button
          type="button"
          style={buttonStyle}
          onClick={() => void runValidation()}
        >
          Validate dataset
        </button>
        <button
          type="button"
          style={buttonStyle}
          onClick={() => void findDuplicates()}
        >
          Find duplicates
        </button>
        <div style={splitRowStyle}>
          <input
            aria-label="Split output path"
            style={inputStyle}
            value={splitOutputPath}
            onChange={(event) => setSplitOutputPath(event.target.value)}
          />
          <button
            type="button"
            style={buttonStyle}
            onClick={() => void splitDataset()}
          >
            Split dataset
          </button>
        </div>
      </section>

      <div style={gridStyle}>
        <ClassDistribution classes={classes} />
        <section style={statsPanelStyle}>
          <h3 style={{ margin: 0 }}>Key Stats</h3>
          <dl style={definitionListStyle}>
            <div>
              <dt style={termStyle}>Format</dt>
              <dd style={definitionStyle}>
                {String(inspectResult?.["format_detected"] ?? "n/a")}
              </dd>
            </div>
            <div>
              <dt style={termStyle}>Annotations</dt>
              <dd style={definitionStyle}>
                {String(inspectResult?.["total_annotations"] ?? 0)}
              </dd>
            </div>
            <div>
              <dt style={termStyle}>Classes</dt>
              <dd style={definitionStyle}>
                {String(inspectResult?.["num_classes"] ?? 0)}
              </dd>
            </div>
            <div>
              <dt style={termStyle}>Orphan images</dt>
              <dd style={definitionStyle}>
                {String(inspectResult?.["orphan_images"] ?? 0)}
              </dd>
            </div>
          </dl>
          <div style={{ display: "grid", gap: "6px" }}>
            <strong>Warnings</strong>
            {warnings.length ? (
              warnings.map((warning) => <span key={warning}>{warning}</span>)
            ) : (
              <span style={mutedStyle}>No warnings.</span>
            )}
          </div>
        </section>
      </div>

      {missingLabelImages.length ? (
        <section style={issuePanelStyle}>
          <h3 style={{ margin: 0 }}>Missing labels</h3>
          {missingLabelImages.slice(0, 25).map((imagePath) => (
            <div key={imagePath} style={issueRowStyle}>
              <code style={pathStyle}>{imagePath}</code>
              <button
                type="button"
                style={secondaryButtonStyle}
                onClick={() =>
                  postToExtension({ type: "openPath", path: imagePath })
                }
              >
                Jump to File
              </button>
            </div>
          ))}
        </section>
      ) : null}

      {bboxSizeBuckets ? (
        <section style={statsPanelStyle}>
          <h3 style={{ margin: 0 }}>Bounding box size distribution</h3>
          <div style={bucketGridStyle}>
            {Object.entries(bboxSizeBuckets).map(([bucket, count]) => (
              <span key={bucket} style={bucketStyle}>
                <strong>{bucket}</strong>
                <span>{count}</span>
              </span>
            ))}
          </div>
        </section>
      ) : null}

      {confusionMatrix.length ? (
        <section style={statsPanelStyle}>
          <h3 style={{ margin: 0 }}>Confusion matrix</h3>
          {confusionMatrix.map((entry) => (
            <div
              key={`${entry.true_class}-${entry.predicted_class}`}
              style={issueRowStyle}
            >
              <span>
                {entry.true_class} {"->"} {entry.predicted_class}
              </span>
              <strong>{entry.count}</strong>
            </div>
          ))}
        </section>
      ) : null}

      <SamplePreview samples={initial.samplePreviews} />
    </main>
  );

  async function runValidation(): Promise<void> {
    try {
      const result = await invokeTool<{ summary: string }>(
        clientConfig,
        "dataset_validate",
        {
          dataset_path: initial.datasetPath,
        },
      );
      setStatusMessage(result.summary);
      setError(null);
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : String(nextError),
      );
    }
  }

  async function findDuplicates(): Promise<void> {
    try {
      const result = await invokeTool<{ total_duplicates: number }>(
        clientConfig,
        "dataset_find_duplicates",
        {
          dataset_path: initial.datasetPath,
        },
      );
      setStatusMessage(`Detected ${result.total_duplicates} duplicate images.`);
      setError(null);
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : String(nextError),
      );
    }
  }

  async function splitDataset(): Promise<void> {
    try {
      const result = await invokeTool<{ output_path: string }>(
        clientConfig,
        "dataset_split",
        {
          dataset_path: initial.datasetPath,
          output_path: splitOutputPath,
          overwrite: true,
          confirm: true,
        },
      );
      setStatusMessage(`Split dataset written to ${result.output_path}.`);
      setError(null);
      setInspectResult((current) => current);
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : String(nextError),
      );
    }
  }
}

function parseNumberRecord(value: unknown): Record<string, number> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const entries = Object.entries(value as Record<string, unknown>).filter(
    (entry): entry is [string, number] => typeof entry[1] === "number",
  );
  return entries.length ? Object.fromEntries(entries) : null;
}

function isConfusionEntry(value: unknown): value is {
  true_class: string;
  predicted_class: string;
  count: number;
} {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Record<string, unknown>;
  return (
    typeof record["true_class"] === "string" &&
    typeof record["predicted_class"] === "string" &&
    typeof record["count"] === "number"
  );
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "24px",
  boxSizing: "border-box",
  background:
    "radial-gradient(circle at top left, var(--vscode-sideBar-background), var(--vscode-editor-background) 60%)",
  color: "var(--vscode-editor-foreground)",
  fontFamily: "var(--vscode-font-family)",
  display: "grid",
  gap: "20px",
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
  fontSize: "28px",
  lineHeight: "1.2",
  wordBreak: "break-word",
};

const statBadgeStyle: CSSProperties = {
  padding: "10px 14px",
  borderRadius: "999px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editorWidget-background)",
};

const actionPanelStyle: CSSProperties = {
  display: "grid",
  gap: "12px",
  padding: "16px",
  borderRadius: "16px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const splitRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr auto",
  gap: "12px",
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "10px 12px",
  borderRadius: "10px",
  border: "1px solid var(--vscode-input-border)",
  background: "var(--vscode-input-background)",
  color: "var(--vscode-input-foreground)",
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

const issuePanelStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  padding: "16px",
  borderRadius: "12px",
  border: "1px solid var(--vscode-inputValidation-errorBorder)",
  background: "var(--vscode-inputValidation-errorBackground)",
};

const issueRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto",
  gap: "10px",
  alignItems: "center",
};

const pathStyle: CSSProperties = {
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const bucketGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: "10px",
};

const bucketStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  padding: "10px 12px",
  borderRadius: "8px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editorWidget-background)",
};

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: "20px",
};

const statsPanelStyle: CSSProperties = {
  display: "grid",
  gap: "14px",
  padding: "16px",
  borderRadius: "16px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const definitionListStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
  gap: "12px",
  margin: 0,
};

const termStyle: CSSProperties = {
  marginBottom: "4px",
  color: "var(--vscode-descriptionForeground)",
  fontSize: "12px",
};

const definitionStyle: CSSProperties = {
  margin: 0,
  fontSize: "16px",
  fontWeight: "700",
};

const mutedStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: "12px",
};

const errorStyle: CSSProperties = {
  padding: "12px 16px",
  borderRadius: "12px",
  background: "var(--vscode-inputValidation-errorBackground)",
  border: "1px solid var(--vscode-inputValidation-errorBorder)",
};

const successStyle: CSSProperties = {
  padding: "12px 16px",
  borderRadius: "12px",
  background: "var(--vscode-inputValidation-infoBackground)",
  border: "1px solid var(--vscode-inputValidation-infoBorder)",
};

const rootNode = document.getElementById("root");
if (rootNode) {
  createRoot(rootNode).render(<DatasetInspectorApp />);
}

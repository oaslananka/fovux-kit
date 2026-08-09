import { isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DeploymentAdvisorPanel } from "../../src/webviews/exportWizard/components/DeploymentAdvisorPanel";
import type { DeploymentAdviseResult } from "../../src/webviews/exportWizard/targets";
import type { ExportWizardModelArtifact } from "../../src/webviews/shared/types";

const MODEL: ExportWizardModelArtifact = {
  name: "best.pt",
  path: "/runs/best.pt",
  format: "pt",
  source: "training",
};

const RESULT: DeploymentAdviseResult = {
  target_profile: "cpu_server",
  model_path: MODEL.path,
  format: "onnx",
  model_size_mb: 12.5,
  compatibility_preflight: { compatible: true, details: "Runtime and operators are supported." },
  quantization_recommendation: "INT8 is recommended for this target.",
  readiness_score: 86,
  parity_check: {
    checked: true,
    max_coordinate_diff: 0.002,
    class_match_rate: 0.98,
    details: "Parity is within the deployment threshold.",
  },
  benchmark_results: {
    latency_p50_ms: 12.3,
    latency_p95_ms: 18.7,
    throughput_fps: 55.4,
    peak_memory_mb: 128.2,
    benchmarked_locally: true,
  },
  risk_warnings: ["Confirm accelerator availability before rollout."],
  runtime_snippets: {
    python: "python-snippet",
    node: "node-snippet",
    docker: "docker-snippet",
  },
  report_path: "/reports/deployment.md",
};

describe("deployment advisor panel", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders the controlled advisor state and deployment result", () => {
    const markup = renderToStaticMarkup(
      <DeploymentAdvisorPanel
        models={[MODEL]}
        modelPath={MODEL.path}
        targetProfile="cpu_server"
        datasetPath="/data/val"
        result={RESULT}
        isRunning={false}
        snippetTab="python"
        onModelPathChange={vi.fn()}
        onTargetProfileChange={vi.fn()}
        onDatasetPathChange={vi.fn()}
        onSnippetTabChange={vi.fn()}
        onRun={vi.fn()}
        onOpenPath={vi.fn()}
      />
    );

    expect(markup).toContain("Select Model Artifact");
    expect(markup).toContain("best.pt · PT (training)");
    expect(markup).toContain("Readiness Score");
    expect(markup).toContain("86/100");
    expect(markup).toContain("Runtime and operators are supported.");
    expect(markup).toContain("INT8 is recommended for this target.");
    expect(markup).toContain("98%");
    expect(markup).toContain("18.7 ms");
    expect(markup).toContain("Confirm accelerator availability before rollout.");
    expect(markup).toContain("python-snippet");
  });

  it("forwards controlled form and result actions", () => {
    const callbacks = {
      model: vi.fn(),
      target: vi.fn(),
      dataset: vi.fn(),
      snippet: vi.fn(),
      run: vi.fn(),
      openPath: vi.fn(),
    };
    const tree = DeploymentAdvisorPanel({
      models: [MODEL],
      modelPath: MODEL.path,
      targetProfile: "cpu_server",
      datasetPath: "/data/val",
      result: RESULT,
      isRunning: false,
      snippetTab: "python",
      onModelPathChange: callbacks.model,
      onTargetProfileChange: callbacks.target,
      onDatasetPathChange: callbacks.dataset,
      onSnippetTabChange: callbacks.snippet,
      onRun: callbacks.run,
      onOpenPath: callbacks.openPath,
    });

    triggerValue(tree, "Select Model", "/runs/other.pt");
    triggerValue(tree, "Target Profile", "jetson");
    triggerValue(tree, "Validation Dataset", "/data/new");
    requireButton(tree, "Run Deployment Advisor").props.onClick();
    requireButton(tree, "Reveal Markdown Report").props.onClick();
    requireButton(tree, "Node.js").props.onClick();

    expect(callbacks.model).toHaveBeenCalledWith("/runs/other.pt");
    expect(callbacks.target).toHaveBeenCalledWith("jetson");
    expect(callbacks.dataset).toHaveBeenCalledWith("/data/new");
    expect(callbacks.run).toHaveBeenCalledOnce();
    expect(callbacks.openPath).toHaveBeenCalledWith(RESULT.report_path);
    expect(callbacks.snippet).toHaveBeenCalledWith("node");
  });

  it("renders empty and running states without a deployment result", () => {
    const markup = renderToStaticMarkup(
      <DeploymentAdvisorPanel
        models={[]}
        modelPath=""
        targetProfile="cpu_server"
        datasetPath=""
        result={null}
        isRunning
        snippetTab="python"
        onModelPathChange={vi.fn()}
        onTargetProfileChange={vi.fn()}
        onDatasetPathChange={vi.fn()}
        onSnippetTabChange={vi.fn()}
        onRun={vi.fn()}
        onOpenPath={vi.fn()}
      />
    );

    expect(markup).toContain("No models available");
    expect(markup).toContain("Analyzing...");
    expect(markup).not.toContain("Readiness Score");
  });

  it("renders fallback result branches and copies an unavailable snippet as empty text", () => {
    const fallbackResult: DeploymentAdviseResult = {
      ...RESULT,
      readiness_score: 55,
      compatibility_preflight: { compatible: false, details: "Unsupported operator detected." },
      risk_warnings: [],
      parity_check: {
        checked: false,
        max_coordinate_diff: 0,
        class_match_rate: 0,
        details: "Parity was not requested.",
      },
      benchmark_results: { ...RESULT.benchmark_results, benchmarked_locally: false },
      runtime_snippets: {},
    };
    const clipboard = { writeText: vi.fn() };
    vi.stubGlobal("navigator", { clipboard });
    const props = {
      models: [MODEL],
      modelPath: MODEL.path,
      targetProfile: "cpu_server",
      datasetPath: "",
      result: fallbackResult,
      isRunning: false,
      snippetTab: "ruby",
      onModelPathChange: vi.fn(),
      onTargetProfileChange: vi.fn(),
      onDatasetPathChange: vi.fn(),
      onSnippetTabChange: vi.fn(),
      onRun: vi.fn(),
      onOpenPath: vi.fn(),
    };
    const tree = DeploymentAdvisorPanel(props);
    const markup = renderToStaticMarkup(tree);

    expect(markup).toContain("Unsupported operator detected.");
    expect(markup).toContain("Parity was not requested.");
    expect(markup).toContain("Estimated");
    expect(markup).toContain("Snippet not available");
    expect(markup).toContain("var(--vscode-charts-orange)");
    expect(markup).not.toContain("Warnings &amp; Risks Detected");

    requireButton(tree, "Copy").props.onClick();
    expect(clipboard.writeText).toHaveBeenCalledWith("");
  });
});

function triggerValue(root: ReactElement, label: string, value: string): void {
  const element = requireElement(
    root,
    (candidate) => (candidate.props as { "aria-label"?: string })["aria-label"] === label,
    label
  );
  (element.props as { onChange: (event: { target: { value: string } }) => void }).onChange({
    target: { value },
  });
}

function requireButton(root: ReactElement, label: string): ReactElement {
  return requireElement(
    root,
    (candidate) =>
      candidate.type === "button" &&
      String((candidate.props as { children?: ReactNode }).children).includes(label),
    label
  );
}

function requireElement(
  node: ReactNode,
  predicate: (element: ReactElement) => boolean,
  description: string
): ReactElement {
  const match = findElement(node, predicate);
  if (!match) throw new Error(`Missing ${description}`);
  return match;
}

function findElement(
  node: ReactNode,
  predicate: (element: ReactElement) => boolean
): ReactElement | null {
  if (Array.isArray(node)) {
    for (const child of node) {
      const match = findElement(child, predicate);
      if (match) return match;
    }
    return null;
  }
  if (!isValidElement(node)) return null;
  if (predicate(node)) return node;
  const children = (node.props as { children?: ReactNode }).children;
  for (const child of Array.isArray(children) ? children : [children]) {
    const match = findElement(child, predicate);
    if (match) return match;
  }
  return null;
}

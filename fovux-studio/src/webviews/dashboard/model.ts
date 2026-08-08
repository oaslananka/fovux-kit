import type { ChartSeries } from "./components/MetricChart";
import type { MetricPayload } from "../shared/api";
import type { DashboardInitialState } from "../shared/types";

export const COLORS = [
  "var(--vscode-charts-blue)",
  "var(--vscode-charts-orange)",
  "var(--vscode-charts-purple)",
  "var(--vscode-charts-green)",
  "var(--vscode-charts-red)",
];
export const MAP50_KEYS = [
  "metrics/mAP50(B)",
  "map50",
  "mAP50",
  "metrics/map50",
  "metrics/mAP50",
];
export const BOX_LOSS_KEYS = ["train/box_loss", "loss/box", "box_loss", "box"];

export interface NextAction {
  title: string;
  description: string;
  ctaText: string;
  type: "startServer" | "initializeDemoWorkspace" | "triggerCommand";
  command?: string;
  args?: unknown[];
}

export function calculateNextAction(state: DashboardInitialState, hasRuns: boolean): NextAction {
  if (!state.isServerReachable) {
    return {
      title: "Start Fovux Local Server",
      description:
        "Connect Fovux Studio to the python-based MCP tool suite to begin model training and evaluation.",
      ctaText: "Start Server",
      type: "startServer",
    };
  }

  const hasDatasets = !!(state.discoveredDatasets && state.discoveredDatasets.length > 0);
  if (!hasRuns && !hasDatasets) {
    return {
      title: "Set Up a Demo Workspace",
      description:
        "Initialize a sample YOLO dataset, pre-trained base model, and mock run logs with just one click.",
      ctaText: "Initialize Demo Workspace",
      type: "initializeDemoWorkspace",
    };
  }
  if (hasDatasets && !hasRuns) {
    return {
      title: "Inspect Discovered Dataset",
      description:
        "A dataset yaml was detected in your workspace. Inspect classes, label health, and check splits.",
      ctaText: "Open Dataset Inspector",
      type: "triggerCommand",
      command: "fovux.openDatasetInspector",
      args: [state.discoveredDatasets?.[0]],
    };
  }
  const activeRun = state.initialRuns.find((run) => run.status === "running");
  if (activeRun) {
    return {
      title: "Monitor Active Training",
      description: `Run "${activeRun.id}" is currently training. Watch losses, live metric streams, and epoch curves.`,
      ctaText: "Focus Running Training",
      type: "triggerCommand",
      command: "fovux.openDashboard",
    };
  }
  return {
    title: "Export Finished Model",
    description:
      "Your YOLO training runs are complete. Package the model to ONNX or TFLite for edge deployment.",
    ctaText: "Open Export Wizard",
    type: "triggerCommand",
    command: "fovux.openExportWizard",
  };
}

export function upsertPayload(series: MetricPayload[], payload: MetricPayload): MetricPayload[] {
  const nextSeries = series.filter((item) => item.epoch !== payload.epoch);
  nextSeries.push(payload);
  nextSeries.sort((left, right) => left.epoch - right.epoch);
  return nextSeries;
}

export function toChartSeries(
  runId: string,
  series: MetricPayload[],
  metricKeys: string[],
  colorIndex: number
): ChartSeries | null {
  const points = series
    .map((item) => ({ x: item.epoch, y: readMetric(item.metrics, metricKeys) }))
    .filter((point): point is { x: number; y: number } => typeof point.y === "number");
  if (!points.length) {
    return null;
  }
  return {
    label: runId,
    color: COLORS[colorIndex % COLORS.length],
    points,
  };
}

export function readMetric(metrics: Record<string, number>, keys: string[]): number | undefined {
  for (const key of keys) {
    const value = metrics[key];
    if (typeof value === "number") {
      return value;
    }
  }
  return undefined;
}

export function formatMetric(value: number | undefined): string {
  return typeof value === "number" ? value.toFixed(3) : "n/a";
}

export function truncatePath(path: string): string {
  if (path.length <= 40) return path;
  return "..." + path.slice(-37);
}

export function getBasename(path: string): string {
  return path.split(/[/\\]/).pop() || path;
}

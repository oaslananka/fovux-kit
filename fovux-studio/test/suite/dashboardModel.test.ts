import { describe, expect, it } from "vitest";

import {
  calculateNextAction,
  formatMetric,
  getBasename,
  readMetric,
  toChartSeries,
  truncatePath,
  upsertPayload,
} from "../../src/webviews/dashboard/model";
import type { MetricPayload } from "../../src/webviews/shared/api";
import type { DashboardInitialState } from "../../src/webviews/shared/types";

const BASE_STATE: DashboardInitialState = {
  baseUrl: "http://127.0.0.1:7823",
  authToken: null,
  pollIntervalMs: 2000,
  initialRuns: [],
  initialError: null,
  isServerReachable: true,
  fovuxHome: "/home/user/.fovux",
  discoveredDatasets: [],
};

describe("dashboard model", () => {
  it("selects a demo-workspace action for an empty connected workspace", () => {
    expect(calculateNextAction(BASE_STATE, false).type).toBe("initializeDemoWorkspace");
  });

  it("upserts metrics by epoch and keeps chronological order", () => {
    const series: MetricPayload[] = [
      { epoch: 2, metrics: { map50: 0.5 } },
      { epoch: 1, metrics: { map50: 0.3 } },
    ];
    const updated = upsertPayload(series, { epoch: 2, metrics: { map50: 0.7 } });

    expect(updated.map((item) => item.epoch)).toEqual([1, 2]);
    expect(updated[1]?.metrics.map50).toBe(0.7);
  });

  it("reads, formats, and shortens display values consistently", () => {
    expect(readMetric({ map50: 0.81234 }, ["missing", "map50"])).toBe(0.81234);
    expect(formatMetric(0.81234)).toBe("0.812");
    expect(getBasename("C:\\runs\\demo")).toBe("demo");
    expect(truncatePath("x".repeat(80))).toHaveLength(40);
  });
  it("selects each workflow action from dashboard state", () => {
    expect(calculateNextAction({ ...BASE_STATE, isServerReachable: false }, false).type).toBe(
      "startServer"
    );
    expect(
      calculateNextAction({ ...BASE_STATE, discoveredDatasets: ["/data/demo.yaml"] }, false)
    ).toMatchObject({
      type: "triggerCommand",
      command: "fovux.openDatasetInspector",
      args: ["/data/demo.yaml"],
    });

    const runningState: DashboardInitialState = {
      ...BASE_STATE,
      initialRuns: [
        {
          id: "run-1",
          status: "running",
          model: "model.pt",
          epochs: 10,
          created_at: null,
        },
      ],
    };
    expect(calculateNextAction(runningState, true)).toMatchObject({
      type: "triggerCommand",
      command: "fovux.openDashboard",
    });

    const finishedState: DashboardInitialState = {
      ...BASE_STATE,
      initialRuns: [
        {
          id: "run-2",
          status: "completed",
          model: "model.pt",
          epochs: 10,
          created_at: null,
        },
      ],
    };
    expect(calculateNextAction(finishedState, true)).toMatchObject({
      type: "triggerCommand",
      command: "fovux.openExportWizard",
    });
  });

  it("builds chart series only when a requested metric is present", () => {
    const payloads: MetricPayload[] = [
      { epoch: 1, metrics: { map50: 0.4 } },
      { epoch: 2, metrics: { loss: 0.3 } },
      { epoch: 3, metrics: { map50: 0.8 } },
    ];

    expect(toChartSeries("run-1", payloads, ["map50"], 6)).toEqual({
      label: "run-1",
      color: "var(--vscode-charts-orange)",
      points: [
        { x: 1, y: 0.4 },
        { x: 3, y: 0.8 },
      ],
    });
    expect(toChartSeries("run-1", payloads, ["missing"], 0)).toBeNull();
  });

  it("handles missing metrics and short display paths", () => {
    expect(readMetric({ map50: 0.5 }, ["missing"])).toBeUndefined();
    expect(formatMetric(undefined)).toBe("n/a");
    expect(truncatePath("short/path")).toBe("short/path");
    expect(getBasename("single-name")).toBe("single-name");
  });

});

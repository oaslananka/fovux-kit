import { describe, expect, it } from "vitest";

import {
  formatMetric,
  sortComparedRuns,
  type ComparedRun,
} from "../../src/webviews/compareRuns/model";

const RUNS: ComparedRun[] = [
  {
    run_id: "slow",
    status: "completed",
    model: "b.pt",
    epochs: 20,
    best_map50: 0.7,
    latency_ms: 30,
    run_path: "/runs/slow",
  },
  {
    run_id: "fast",
    status: "completed",
    model: "a.pt",
    epochs: 10,
    best_map50: 0.8,
    latency_ms: null,
    run_path: "/runs/fast",
  },
];

describe("compare-runs model", () => {
  it("sorts numeric metrics without mutating the response", () => {
    const sorted = sortComparedRuns(RUNS, "best_map50", "desc");

    expect(sorted.map((run) => run.run_id)).toEqual(["fast", "slow"]);
    expect(RUNS.map((run) => run.run_id)).toEqual(["slow", "fast"]);
  });

  it("keeps missing metrics after present metrics for descending sort", () => {
    expect(sortComparedRuns(RUNS, "latency_ms", "desc").map((run) => run.run_id)).toEqual([
      "slow",
      "fast",
    ]);
  });


  it("sorts numeric metrics ascending", () => {
    expect(sortComparedRuns(RUNS, "epochs", "asc").map((run) => run.run_id)).toEqual([
      "fast",
      "slow",
    ]);
  });

  it("sorts string metrics in both directions", () => {
    expect(sortComparedRuns(RUNS, "model", "asc").map((run) => run.run_id)).toEqual([
      "fast",
      "slow",
    ]);
    expect(sortComparedRuns(RUNS, "model", "desc").map((run) => run.run_id)).toEqual([
      "slow",
      "fast",
    ]);
  });

  it("places missing metrics first for ascending sort", () => {
    expect(sortComparedRuns(RUNS, "latency_ms", "asc").map((run) => run.run_id)).toEqual([
      "fast",
      "slow",
    ]);
  });

  it("keeps stable order when compared values have different types", () => {
    const mixed: ComparedRun[] = [
      { ...RUNS[0]!, model: "same", config: { source: "a" } },
      { ...RUNS[1]!, model: "same", config: { source: "b" } },
    ];
    expect(sortComparedRuns(mixed, "config", "asc").map((run) => run.run_id)).toEqual([
      "slow",
      "fast",
    ]);
  });
  it("formats optional metrics consistently", () => {
    expect(formatMetric(0.81234)).toBe("0.8123");
    expect(formatMetric(null)).toBe("n/a");
  });
});

import { describe, expect, it } from "vitest";

import {
  buildTrainingPayload,
  evaluateTrainingPreflight,
} from "../../src/webviews/trainingLauncher/model";

describe("training launcher model", () => {
  it("builds a normalized training payload from form values", () => {
    expect(
      buildTrainingPayload({
        runName: "  edge-run  ",
        datasetPath: "  /data/yolo  ",
        model: "  yolo11n.pt  ",
        epochs: 42,
        batch: 8,
        imgsz: 512,
        device: "cpu",
        tags: " baseline, edge, , int8 ",
        extraArgs: '{"workers":2}',
        force: true,
        maxConcurrentRuns: 2.9,
      })
    ).toEqual({
      dataset_path: "/data/yolo",
      model: "yolo11n.pt",
      epochs: 42,
      batch: 8,
      imgsz: 512,
      device: "cpu",
      tags: ["baseline", "edge", "int8"],
      extra_args: { workers: 2 },
      name: "edge-run",
      force: true,
      max_concurrent_runs: 2,
    });
  });

  it("blocks launch and maps preflight guidance when force is disabled", () => {
    expect(
      evaluateTrainingPreflight(
        {
          ready: false,
          blockers: ["dataset is not valid"],
          next_actions: ["Run dataset validation"],
        },
        false
      )
    ).toEqual({
      blocked: true,
      errorMessage:
        "Training preflight blocked launch.\n- dataset is not valid\nNext: Run dataset validation",
      approvalReason: undefined,
    });
  });

  it("allows a forced launch and returns the preflight approval reason", () => {
    expect(
      evaluateTrainingPreflight(
        {
          ready: false,
          blockers: ["GPU capacity is below the requested batch size", "dataset warning"],
          next_actions: ["Reduce the batch size"],
        },
        true
      )
    ).toEqual({
      blocked: false,
      errorMessage: null,
      approvalReason:
        "Studio force override after preflight blockers: GPU capacity is below the requested batch size; dataset warning",
    });
  });

  it("rejects a blank dataset path", () => {
    expect(() =>
      buildTrainingPayload({
        runName: "",
        datasetPath: "   ",
        model: "yolo11n.pt",
        epochs: 10,
        batch: 16,
        imgsz: 640,
        device: "auto",
        tags: "baseline",
        extraArgs: "{}",
        force: false,
        maxConcurrentRuns: 1,
      })
    ).toThrow("Dataset path is required.");
  });

  it("rejects extra args that are not a JSON object", () => {
    expect(() =>
      buildTrainingPayload({
        runName: "",
        datasetPath: "/data/yolo",
        model: "yolo11n.pt",
        epochs: 10,
        batch: 16,
        imgsz: 640,
        device: "auto",
        tags: "baseline",
        extraArgs: "[]",
        force: false,
        maxConcurrentRuns: 1,
      })
    ).toThrow("Extra args must be a JSON object.");
  });

  it("keeps a clean preflight unblocked without approval metadata", () => {
    expect(evaluateTrainingPreflight({ ready: true }, false)).toEqual({
      blocked: false,
      errorMessage: null,
      approvalReason: undefined,
    });
  });
});

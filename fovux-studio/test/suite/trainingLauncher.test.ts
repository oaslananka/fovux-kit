import { beforeEach, describe, expect, it } from "vitest";

import {
  estimateTrainingMinutes,
  TRAINING_PRESETS,
} from "../../src/webviews/trainingLauncher/presets";
import {
  mergePresets,
  parseImportedPresets,
} from "../../src/webviews/trainingLauncher/main";
import { getUserPresets, saveUserPreset } from "../../src/fovux/userPresets";
import { mockGlobalState, resetVscodeMockState } from "./helpers/vscodeMock";
import "./helpers/vscodeMock";

describe("training launcher presets", () => {
  beforeEach(() => {
    resetVscodeMockState();
  });

  it("includes the release presets", () => {
    expect(TRAINING_PRESETS.map((preset) => preset.id)).toEqual(
      expect.arrayContaining([
        "fast_prototype",
        "production",
        "mobile_edge",
        "accuracy_max",
      ]),
    );
  });

  it("estimates a non-zero training duration", () => {
    expect(estimateTrainingMinutes(30, 16, 640)).toBeGreaterThanOrEqual(5);
  });

  it("persists user presets in VS Code globalState", async () => {
    const context = { globalState: mockGlobalState };
    await saveUserPreset(context as never, {
      name: "edge baseline",
      createdAt: "2026-04-27T00:00:00.000Z",
      config: {
        model: "yolov8n.pt",
        epochs: 50,
        batch: 16,
        imgsz: 640,
        device: "auto",
        tags: "edge",
        extraArgs: "{}",
        maxConcurrentRuns: 1,
      },
    });

    expect(getUserPresets(context as never)).toHaveLength(1);
    expect(mockGlobalState.update).toHaveBeenCalledWith(
      "fovux.userPresets",
      expect.any(Array),
    );
  });

  it("replaces duplicate user preset names instead of storing stale copies", async () => {
    const context = { globalState: mockGlobalState };
    await saveUserPreset(context as never, {
      name: "production",
      createdAt: "2026-04-27T00:00:00.000Z",
      config: {
        model: "yolov8n.pt",
        epochs: 20,
        batch: 8,
        imgsz: 640,
        device: "auto",
        tags: "first",
        extraArgs: "{}",
        maxConcurrentRuns: 1,
      },
    });
    await saveUserPreset(context as never, {
      name: "production",
      createdAt: "2026-04-28T00:00:00.000Z",
      config: {
        model: "yolov8m.pt",
        epochs: 80,
        batch: 16,
        imgsz: 768,
        device: "0",
        tags: "replacement",
        extraArgs: "{}",
        maxConcurrentRuns: 1,
      },
    });

    const presets = getUserPresets(context as never);

    expect(presets).toHaveLength(1);
    expect(presets[0]?.config.model).toBe("yolov8m.pt");
    expect(presets[0]?.config.tags).toBe("replacement");
  });

  it("validates imported preset JSON and replaces duplicate names in memory", () => {
    const imported = parseImportedPresets(
      JSON.stringify({
        presets: [
          {
            name: "imported",
            createdAt: "2026-04-28T00:00:00.000Z",
            config: {
              model: "yolov8n.pt",
              epochs: 30,
              batch: 16,
              imgsz: 640,
              device: "auto",
              tags: "json",
              extraArgs: "{}",
              maxConcurrentRuns: 1,
            },
          },
          { name: "invalid", config: {} },
        ],
      }),
    );

    const merged = mergePresets(imported, [
      {
        name: "imported",
        createdAt: "2026-04-27T00:00:00.000Z",
        config: {
          model: "old.pt",
          epochs: 1,
          batch: 1,
          imgsz: 320,
          device: "auto",
          tags: "old",
          extraArgs: "{}",
          maxConcurrentRuns: 1,
        },
      },
    ]);

    expect(imported).toHaveLength(1);
    expect(merged).toHaveLength(1);
    expect(merged[0]?.config.model).toBe("yolov8n.pt");
  });
});

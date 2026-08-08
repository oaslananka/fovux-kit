/* eslint-disable @typescript-eslint/no-explicit-any */
import "./helpers/vscodeMock";
import { createdPanels, resetVscodeMockState } from "./helpers/vscodeMock";

import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, expect, it, vi } from "vitest";

import {
  annotationEditorReducer,
  createAnnotationEditorState,
} from "../../src/webviews/annotationEditor/model";
import { openAnnotationEditor } from "../../src/commands/openAnnotationEditor";

describe("annotation editor reducer", () => {
  it("draws boxes and supports undo", () => {
    let state = createAnnotationEditorState([]);
    state = annotationEditorReducer(state, {
      type: "beginDraw",
      classId: 0,
      className: "object",
      point: { x: 0.1, y: 0.2 },
    });
    state = annotationEditorReducer(state, {
      type: "pointerMove",
      point: { x: 0.4, y: 0.6 },
    });
    state = annotationEditorReducer(state, {
      type: "pointerUp",
      point: { x: 0.4, y: 0.6 },
    });

    expect(state.boxes).toHaveLength(1);
    expect(state.boxes[0]?.x).toBeCloseTo(0.1);
    expect(state.boxes[0]?.y).toBeCloseTo(0.2);
    expect(state.boxes[0]?.width).toBeCloseTo(0.3);
    expect(state.boxes[0]?.height).toBeCloseTo(0.4);

    state = annotationEditorReducer(state, { type: "undo" });

    expect(state.boxes).toEqual([]);
  });

  it("moves, resizes, and deletes the selected box", () => {
    let state = createAnnotationEditorState([
      {
        classId: 0,
        className: "object",
        x: 0.2,
        y: 0.2,
        width: 0.2,
        height: 0.2,
      },
    ]);

    state = annotationEditorReducer(state, {
      type: "beginMove",
      index: 0,
      point: { x: 0.2, y: 0.2 },
    });
    state = annotationEditorReducer(state, {
      type: "pointerMove",
      point: { x: 0.3, y: 0.4 },
    });
    state = annotationEditorReducer(state, {
      type: "pointerUp",
      point: { x: 0.3, y: 0.4 },
    });

    expect(state.boxes[0]).toMatchObject({ x: 0.3, y: 0.4 });

    state = annotationEditorReducer(state, {
      type: "beginResize",
      index: 0,
      handle: "se",
      point: { x: 0.5, y: 0.6 },
    });
    state = annotationEditorReducer(state, {
      type: "pointerUp",
      point: { x: 0.7, y: 0.8 },
    });

    expect(state.boxes[0]?.width).toBeCloseTo(0.4);
    expect(state.boxes[0]?.height).toBeCloseTo(0.4);

    state = annotationEditorReducer(state, { type: "deleteSelected" });

    expect(state.boxes).toEqual([]);
  });

  it("resets state with new boxes", () => {
    let state = createAnnotationEditorState([]);
    state = annotationEditorReducer(state, {
      type: "reset",
      boxes: [
        {
          classId: 1,
          className: "person",
          x: 0.1,
          y: 0.1,
          width: 0.5,
          height: 0.5,
        },
      ],
      status: "Reset status",
    });

    expect(state.boxes).toHaveLength(1);
    expect(state.boxes[0]?.className).toBe("person");
    expect(state.status).toBe("Reset status");
  });


  it("handles no-op editor actions without creating history", () => {
    const state = createAnnotationEditorState([]);

    expect(
      annotationEditorReducer(state, { type: "beginMove", index: 4, point: { x: 0, y: 0 } })
    ).toBe(state);
    expect(
      annotationEditorReducer(state, {
        type: "beginResize",
        index: 4,
        handle: "nw",
        point: { x: 0, y: 0 },
      })
    ).toBe(state);
    expect(annotationEditorReducer(state, { type: "deleteSelected" })).toBe(state);
    expect(annotationEditorReducer(state, { type: "clear" })).toBe(state);
    expect(annotationEditorReducer(state, { type: "undo" })).toBe(state);
    expect(annotationEditorReducer(state, { type: "pointerMove", point: { x: 0, y: 0 } })).toBe(
      state
    );
  });

  it("rejects tiny drafts and supports selection, status, and clear", () => {
    let state = createAnnotationEditorState([
      {
        classId: 0,
        className: "object",
        x: 0.1,
        y: 0.1,
        width: 0.2,
        height: 0.2,
      },
    ]);
    state = annotationEditorReducer(state, { type: "select", index: 0 });
    expect(state.selectedIndex).toBe(0);
    state = annotationEditorReducer(state, { type: "status", status: "Saved" });
    expect(state.status).toBe("Saved");
    state = annotationEditorReducer(state, { type: "clear" });
    expect(state.boxes).toEqual([]);
    state = annotationEditorReducer(state, { type: "undo" });
    expect(state.boxes).toHaveLength(1);

    state = annotationEditorReducer(state, {
      type: "beginDraw",
      classId: 1,
      className: "tiny",
      point: { x: 0.2, y: 0.2 },
    });
    state = annotationEditorReducer(state, { type: "pointerUp", point: { x: 0.201, y: 0.201 } });
    expect(state.boxes).toHaveLength(1);
    expect(state.draft).toBeNull();
  });

  it("keeps unchanged moves out of history and previews northwest resize", () => {
    let state = createAnnotationEditorState([
      {
        classId: 0,
        className: "object",
        x: 0.2,
        y: 0.2,
        width: 0.3,
        height: 0.3,
      },
    ]);
    state = annotationEditorReducer(state, {
      type: "beginMove",
      index: 0,
      point: { x: 0.2, y: 0.2 },
    });
    state = annotationEditorReducer(state, { type: "pointerUp", point: { x: 0.2, y: 0.2 } });
    expect(state.history).toEqual([]);

    state = annotationEditorReducer(state, {
      type: "beginResize",
      index: 0,
      handle: "nw",
      point: { x: 0.2, y: 0.2 },
    });
    state = annotationEditorReducer(state, { type: "pointerMove", point: { x: 0.1, y: 0.1 } });
    expect(state.boxes[0]).toMatchObject({ x: 0.1, y: 0.1, width: 0.4, height: 0.4 });
  });
  it("opens the queue mode editor and loads queue items", async () => {
    resetVscodeMockState();

    const home = fs.mkdtempSync(path.join(os.tmpdir(), "fovux-home-test-"));
    process.env["FOVUX_HOME"] = home;
    fs.writeFileSync(path.join(home, "auth.token"), "token\n");

    const mockQueueItem = {
      id: "entry_123",
      image_path: "/path/to/img.jpg",
      dataset_path: "/path/to/dataset",
      score: 0.95,
      reason: "low_confidence",
      status: "pending",
      predictions: [
        {
          class_id: 0,
          class_name: "cat",
          confidence: 0.45,
          bbox_xyxy: [0.1, 0.2, 0.3, 0.4],
        },
      ],
    };

    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("active_learning_queue_list")) {
        return {
          ok: true,
          json: async () => ({ queue_entries: [mockQueueItem] }),
        };
      }
      if (url.includes("dataset_inspect")) {
        return {
          ok: true,
          json: async () => ({ classes: [{ name: "cat" }] }),
        };
      }
      return { ok: true, json: async () => ({}) };
    });
    vi.stubGlobal("fetch", fetchMock);

    const context = {
      extensionUri: { fsPath: "/dummy/ext", path: "/dummy/ext" },
    };

    await openAnnotationEditor(context as any, {
      isQueueMode: true,
      datasetPath: "/path/to/dataset",
    });

    expect(createdPanels).toHaveLength(1);
    expect(createdPanels[0].title).toBe("Fovux Annotation Editor Queue");

    fs.rmSync(home, { recursive: true, force: true });
    delete process.env["FOVUX_HOME"];
    vi.restoreAllMocks();
  });
});

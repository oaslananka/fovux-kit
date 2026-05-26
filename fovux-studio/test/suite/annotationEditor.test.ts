import { describe, expect, it } from "vitest";

import {
  annotationEditorReducer,
  createAnnotationEditorState,
} from "../../src/webviews/annotationEditor/main";

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
});

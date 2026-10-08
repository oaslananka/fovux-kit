import { describe, expect, it, vi } from "vitest";

import { createAnnotationPointerController } from "../../src/webviews/annotationEditor/controller";
import type { AnnotationEditorAction } from "../../src/webviews/annotationEditor/model";

function makeStage() {
  return {
    focus: vi.fn(),
    setPointerCapture: vi.fn(),
    getBoundingClientRect: () => ({ left: 10, top: 20, width: 200, height: 100 }),
  };
}

function makeEvent(currentTarget: object, clientX = 110, clientY = 70) {
  return {
    currentTarget,
    clientX,
    clientY,
    pointerId: 7,
    stopPropagation: vi.fn(),
  };
}

describe("annotation pointer controller", () => {
  it("normalizes stage draw events and resolves the active class", () => {
    const stage = makeStage();
    const dispatch = vi.fn<(action: AnnotationEditorAction) => void>();
    const controller = createAnnotationPointerController({
      stageRef: { current: stage as never },
      classNames: ["cat", "dog"],
      classId: 1,
      dispatch,
    });
    const event = makeEvent(stage);

    controller.onStagePointerDown(event as never);

    expect(stage.focus).toHaveBeenCalled();
    expect(stage.setPointerCapture).toHaveBeenCalledWith(7);
    expect(dispatch).toHaveBeenCalledWith({
      type: "beginDraw",
      classId: 1,
      className: "dog",
      point: { x: 0.5, y: 0.5 },
    });
  });

  it("forwards move/up/cancel actions and ignores missing stages", () => {
    const stage = makeStage();
    const dispatch = vi.fn<(action: AnnotationEditorAction) => void>();
    const stageRef = { current: stage as never };
    const controller = createAnnotationPointerController({
      stageRef,
      classNames: [],
      classId: 3,
      dispatch,
    });
    const event = makeEvent(stage, 210, 120);

    controller.onStagePointerDown(event as never);
    controller.onStagePointerMove(event as never);
    controller.onStagePointerUp(event as never);
    controller.onStagePointerCancel(event as never);
    expect(dispatch).toHaveBeenNthCalledWith(1, {
      type: "beginDraw",
      classId: 3,
      className: "class_3",
      point: { x: 1, y: 1 },
    });
    expect(dispatch).toHaveBeenNthCalledWith(2, {
      type: "pointerMove",
      point: { x: 1, y: 1 },
    });
    expect(dispatch).toHaveBeenNthCalledWith(3, {
      type: "pointerUp",
      point: { x: 1, y: 1 },
    });
    expect(dispatch).toHaveBeenNthCalledWith(4, { type: "select", index: null });

    stageRef.current = null;
    controller.onStagePointerMove(event as never);
    controller.onStagePointerUp(event as never);
    controller.onBoxPointerDown(0, event as never);
    controller.onResizePointerDown("nw", 0, event as never);
    expect(dispatch).toHaveBeenCalledTimes(4);
  });

  it("translates box and resize events into reducer actions", () => {
    const stage = makeStage();
    const dispatch = vi.fn<(action: AnnotationEditorAction) => void>();
    const controller = createAnnotationPointerController({
      stageRef: { current: stage as never },
      classNames: ["cat"],
      classId: 0,
      dispatch,
    });
    const boxTarget = { setPointerCapture: vi.fn() };
    const event = makeEvent(boxTarget, 60, 45);

    controller.onBoxPointerDown(2, event as never);
    expect(event.stopPropagation).toHaveBeenCalled();
    expect(boxTarget.setPointerCapture).toHaveBeenCalledWith(7);
    expect(dispatch).toHaveBeenLastCalledWith({
      type: "beginMove",
      index: 2,
      point: { x: 0.25, y: 0.25 },
    });

    controller.onResizePointerDown("se", 2, event as never);
    expect(dispatch).toHaveBeenLastCalledWith({
      type: "beginResize",
      handle: "se",
      index: 2,
      point: { x: 0.25, y: 0.25 },
    });
  });
});

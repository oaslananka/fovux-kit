import type { Dispatch, PointerEvent, PointerEventHandler, RefObject } from "react";

import { clamp, type AnnotationEditorAction, type ResizeHandle } from "./model";

export interface AnnotationPointerHandlers {
  onStagePointerDown: PointerEventHandler<HTMLElement>;
  onStagePointerMove: PointerEventHandler<HTMLElement>;
  onStagePointerUp: PointerEventHandler<HTMLElement>;
  onStagePointerCancel: PointerEventHandler<HTMLElement>;
  onBoxPointerDown: (index: number, event: PointerEvent<HTMLSpanElement>) => void;
  onResizePointerDown: (
    handle: ResizeHandle,
    index: number,
    event: PointerEvent<HTMLSpanElement>
  ) => void;
}

interface AnnotationPointerControllerContext {
  stageRef: RefObject<HTMLElement | null>;
  classNames: string[];
  classId: number;
  dispatch: Dispatch<AnnotationEditorAction>;
}

export function createAnnotationPointerController({
  stageRef,
  classNames,
  classId,
  dispatch,
}: Readonly<AnnotationPointerControllerContext>): AnnotationPointerHandlers {
  return {
    onStagePointerDown(event) {
      event.currentTarget.focus();
      event.currentTarget.setPointerCapture(event.pointerId);
      const point = normalizedPoint(event, event.currentTarget);
      const className = classNames[classId] ?? `class_${classId}`;
      dispatch({ type: "beginDraw", classId, className, point });
    },
    onStagePointerMove(event) {
      const target = stageRef.current;
      if (target) {
        dispatch({ type: "pointerMove", point: normalizedPoint(event, target) });
      }
    },
    onStagePointerUp(event) {
      const target = stageRef.current;
      if (target) {
        dispatch({ type: "pointerUp", point: normalizedPoint(event, target) });
      }
    },
    onStagePointerCancel() {
      dispatch({ type: "select", index: null });
    },
    onBoxPointerDown(index, event) {
      const target = stageRef.current;
      if (!target) return;
      event.stopPropagation();
      event.currentTarget.setPointerCapture(event.pointerId);
      dispatch({ type: "beginMove", index, point: normalizedPoint(event, target) });
    },
    onResizePointerDown(handle, index, event) {
      const target = stageRef.current;
      if (!target) return;
      event.stopPropagation();
      event.currentTarget.setPointerCapture(event.pointerId);
      dispatch({
        type: "beginResize",
        handle,
        index,
        point: normalizedPoint(event, target),
      });
    },
  };
}

function normalizedPoint(
  event: Pick<PointerEvent<HTMLElement>, "clientX" | "clientY">,
  target: HTMLElement
): { x: number; y: number } {
  const rect = target.getBoundingClientRect();
  return {
    x: clamp((event.clientX - rect.left) / rect.width),
    y: clamp((event.clientY - rect.top) / rect.height),
  };
}

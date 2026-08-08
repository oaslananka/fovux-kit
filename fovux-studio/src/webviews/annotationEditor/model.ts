import type { DatasetSampleBox } from "../shared/types";

export type Point = { x: number; y: number };
export type ResizeHandle = "nw" | "ne" | "sw" | "se";

export type Interaction =
  | { kind: "idle" }
  | { kind: "draw"; box: DatasetSampleBox; start: Point }
  | {
      kind: "move";
      before: DatasetSampleBox[];
      index: number;
      origin: DatasetSampleBox;
      start: Point;
    }
  | {
      kind: "resize";
      before: DatasetSampleBox[];
      handle: ResizeHandle;
      index: number;
      origin: DatasetSampleBox;
      start: Point;
    };

export interface AnnotationEditorState {
  boxes: DatasetSampleBox[];
  draft: DatasetSampleBox | null;
  history: DatasetSampleBox[][];
  interaction: Interaction;
  selectedIndex: number | null;
  status: string | null;
}

export type AnnotationEditorAction =
  | { type: "beginDraw"; classId: number; className: string; point: Point }
  | { type: "beginMove"; index: number; point: Point }
  | { type: "beginResize"; handle: ResizeHandle; index: number; point: Point }
  | { type: "pointerMove"; point: Point }
  | { type: "pointerUp"; point: Point }
  | { type: "select"; index: number | null }
  | { type: "deleteSelected" }
  | { type: "clear" }
  | { type: "undo" }
  | { type: "reset"; boxes: DatasetSampleBox[]; status: string | null }
  | { type: "status"; status: string | null };

const MIN_BOX_SIZE = 0.005;

export function createAnnotationEditorState(
  boxes: DatasetSampleBox[],
  status: string | null = null
): AnnotationEditorState {
  return {
    boxes,
    draft: null,
    history: [],
    interaction: { kind: "idle" },
    selectedIndex: null,
    status,
  };
}

export function annotationEditorReducer(
  state: AnnotationEditorState,
  action: AnnotationEditorAction
): AnnotationEditorState {
  switch (action.type) {
    case "beginDraw": {
      return {
        ...state,
        draft: {
          classId: action.classId,
          className: action.className,
          x: action.point.x,
          y: action.point.y,
          width: 0,
          height: 0,
        },
        interaction: {
          kind: "draw",
          box: {
            classId: action.classId,
            className: action.className,
            x: action.point.x,
            y: action.point.y,
            width: 0,
            height: 0,
          },
          start: action.point,
        },
        selectedIndex: null,
      };
    }
    case "beginMove": {
      const origin = state.boxes[action.index];
      if (!origin) {
        return state;
      }
      return {
        ...state,
        interaction: {
          kind: "move",
          before: state.boxes,
          index: action.index,
          origin,
          start: action.point,
        },
        selectedIndex: action.index,
      };
    }
    case "beginResize": {
      const origin = state.boxes[action.index];
      if (!origin) {
        return state;
      }
      return {
        ...state,
        interaction: {
          kind: "resize",
          before: state.boxes,
          handle: action.handle,
          index: action.index,
          origin,
          start: action.point,
        },
        selectedIndex: action.index,
      };
    }
    case "pointerMove":
      return applyPointer(state, action.point, false);
    case "pointerUp":
      return applyPointer(state, action.point, true);
    case "select":
      return {
        ...state,
        selectedIndex: action.index,
        interaction: { kind: "idle" },
        draft: null,
      };
    case "deleteSelected": {
      if (state.selectedIndex === null || !state.boxes[state.selectedIndex]) {
        return state;
      }
      return {
        ...state,
        boxes: state.boxes.filter((_box, index) => index !== state.selectedIndex),
        history: pushHistory(state.history, state.boxes),
        interaction: { kind: "idle" },
        selectedIndex: null,
      };
    }
    case "clear":
      if (!state.boxes.length) {
        return state;
      }
      return {
        ...state,
        boxes: [],
        draft: null,
        history: pushHistory(state.history, state.boxes),
        interaction: { kind: "idle" },
        selectedIndex: null,
      };
    case "undo": {
      const previous = state.history.at(-1);
      if (!previous) {
        return state;
      }
      return {
        ...state,
        boxes: previous,
        draft: null,
        history: state.history.slice(0, -1),
        interaction: { kind: "idle" },
        selectedIndex: null,
      };
    }
    case "reset":
      return createAnnotationEditorState(action.boxes, action.status);
    case "status":
      return { ...state, status: action.status };
    default:
      return state;
  }
}

function applyPointer(
  state: AnnotationEditorState,
  point: Point,
  finish: boolean
): AnnotationEditorState {
  switch (state.interaction.kind) {
    case "draw": {
      const draft = normalizeBox(state.interaction.box, point);
      if (!finish) {
        return { ...state, draft };
      }
      if (draft.width < MIN_BOX_SIZE || draft.height < MIN_BOX_SIZE) {
        return { ...state, draft: null, interaction: { kind: "idle" } };
      }
      return {
        ...state,
        boxes: [...state.boxes, draft],
        draft: null,
        history: pushHistory(state.history, state.boxes),
        interaction: { kind: "idle" },
        selectedIndex: state.boxes.length,
      };
    }
    case "move": {
      const nextBox = moveBox(state.interaction.origin, state.interaction.start, point);
      const nextBoxes = replaceBox(state.boxes, state.interaction.index, nextBox);
      if (!finish) {
        return { ...state, boxes: nextBoxes };
      }
      return {
        ...state,
        boxes: nextBoxes,
        history: boxesEqual(state.interaction.before, nextBoxes)
          ? state.history
          : pushHistory(state.history, state.interaction.before),
        interaction: { kind: "idle" },
      };
    }
    case "resize": {
      const nextBox = resizeBox(state.interaction.origin, state.interaction.handle, point);
      const nextBoxes = replaceBox(state.boxes, state.interaction.index, nextBox);
      if (!finish) {
        return { ...state, boxes: nextBoxes };
      }
      return {
        ...state,
        boxes: nextBoxes,
        history: boxesEqual(state.interaction.before, nextBoxes)
          ? state.history
          : pushHistory(state.history, state.interaction.before),
        interaction: { kind: "idle" },
      };
    }
    default:
      return state;
  }
}

function normalizeBox(start: DatasetSampleBox, point: Point): DatasetSampleBox {
  const x = Math.min(start.x, point.x);
  const y = Math.min(start.y, point.y);
  return {
    ...start,
    x,
    y,
    width: Math.abs(point.x - start.x),
    height: Math.abs(point.y - start.y),
  };
}

function moveBox(box: DatasetSampleBox, start: Point, point: Point): DatasetSampleBox {
  const deltaX = point.x - start.x;
  const deltaY = point.y - start.y;
  return {
    ...box,
    x: clamp(box.x + deltaX, 0, 1 - box.width),
    y: clamp(box.y + deltaY, 0, 1 - box.height),
  };
}

function resizeBox(box: DatasetSampleBox, handle: ResizeHandle, point: Point): DatasetSampleBox {
  const left = box.x;
  const top = box.y;
  const right = box.x + box.width;
  const bottom = box.y + box.height;
  const nextLeft = handle.includes("w") ? clamp(point.x, 0, right - MIN_BOX_SIZE) : left;
  const nextRight = handle.includes("e") ? clamp(point.x, left + MIN_BOX_SIZE, 1) : right;
  const nextTop = handle.includes("n") ? clamp(point.y, 0, bottom - MIN_BOX_SIZE) : top;
  const nextBottom = handle.includes("s") ? clamp(point.y, top + MIN_BOX_SIZE, 1) : bottom;
  return {
    ...box,
    x: nextLeft,
    y: nextTop,
    width: nextRight - nextLeft,
    height: nextBottom - nextTop,
  };
}

function replaceBox(
  boxes: DatasetSampleBox[],
  index: number,
  box: DatasetSampleBox
): DatasetSampleBox[] {
  return boxes.map((current, currentIndex) => (currentIndex === index ? box : current));
}

function pushHistory(
  history: DatasetSampleBox[][],
  boxes: DatasetSampleBox[]
): DatasetSampleBox[][] {
  return [...history, boxes].slice(-50);
}

function boxesEqual(left: DatasetSampleBox[], right: DatasetSampleBox[]): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

export function clamp(value: number, min = 0, max = 1): number {
  return Math.max(min, Math.min(max, value));
}

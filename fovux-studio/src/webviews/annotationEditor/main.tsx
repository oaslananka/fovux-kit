import { useReducer, useRef } from "react";
import type { CSSProperties, JSX, KeyboardEvent, PointerEvent } from "react";
import { createRoot } from "react-dom/client";

import {
  postToExtension,
  readInitialState,
  type AnnotationEditorInitialState,
  type DatasetSampleBox,
} from "../shared/types";

type Point = { x: number; y: number };
type ResizeHandle = "nw" | "ne" | "sw" | "se";

type Interaction =
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
  | { type: "status"; status: string | null };

const MIN_BOX_SIZE = 0.005;

function AnnotationEditorApp(): JSX.Element {
  const initial = readInitialState<AnnotationEditorInitialState>({
    imagePath: "",
    imageUri: "",
    classNames: ["class_0"],
    initialBoxes: [],
    initialError: "Initial annotation editor state was not provided.",
  });
  const stageRef = useRef<HTMLElement | null>(null);
  const [classId, setClassId] = useReducer(
    (_current: number, next: number) => next,
    0,
  );
  const [state, dispatch] = useReducer(
    annotationEditorReducer,
    createAnnotationEditorState(initial.initialBoxes, initial.initialError),
  );

  return (
    <main
      style={pageStyle}
      tabIndex={0}
      onKeyDown={(event) => handleKeyDown(event, dispatch)}
    >
      <header style={toolbarStyle}>
        <div>
          <p style={eyebrowStyle}>Annotation Editor</p>
          <h1 style={titleStyle}>Draw YOLO boxes directly on the sample</h1>
        </div>
        <div style={controlsStyle}>
          <select
            aria-label="Class label"
            style={inputStyle}
            value={classId}
            onChange={(event) => setClassId(Number(event.target.value))}
          >
            {initial.classNames.map((name, index) => (
              <option key={name} value={index}>
                {name}
              </option>
            ))}
          </select>
          <button type="button" style={buttonStyle} onClick={save}>
            Save labels
          </button>
          <button
            type="button"
            style={secondaryButtonStyle}
            onClick={() => dispatch({ type: "undo" })}
          >
            Undo
          </button>
          <button
            type="button"
            style={secondaryButtonStyle}
            onClick={() => dispatch({ type: "clear" })}
          >
            Clear
          </button>
        </div>
      </header>

      {state.status ? <p style={statusStyle}>{state.status}</p> : null}

      <section
        ref={stageRef}
        style={stageStyle}
        onPointerDown={(event) => {
          event.currentTarget.focus();
          event.currentTarget.setPointerCapture(event.pointerId);
          const point = normalizedPoint(event, event.currentTarget);
          const className = initial.classNames[classId] ?? `class_${classId}`;
          dispatch({ type: "beginDraw", classId, className, point });
        }}
        onPointerMove={(event) => {
          const target = stageRef.current;
          if (target) {
            dispatch({
              type: "pointerMove",
              point: normalizedPoint(event, target),
            });
          }
        }}
        onPointerUp={(event) => {
          const target = stageRef.current;
          if (target) {
            dispatch({
              type: "pointerUp",
              point: normalizedPoint(event, target),
            });
          }
        }}
        onPointerCancel={() => dispatch({ type: "select", index: null })}
      >
        <img
          src={initial.imageUri}
          alt={initial.imagePath}
          style={imageStyle}
          draggable={false}
        />
        {[...state.boxes, ...(state.draft ? [state.draft] : [])].map(
          (box, index) => {
            const isDraft = index >= state.boxes.length;
            const isSelected = state.selectedIndex === index && !isDraft;
            return (
              <span
                key={`${box.classId}-${box.x}-${box.y}-${index}`}
                style={{
                  ...boxStyle,
                  ...(isSelected ? selectedBoxStyle : null),
                  left: `${box.x * 100}%`,
                  top: `${box.y * 100}%`,
                  width: `${box.width * 100}%`,
                  height: `${box.height * 100}%`,
                }}
                onPointerDown={(event) => {
                  if (isDraft || !stageRef.current) {
                    return;
                  }
                  event.stopPropagation();
                  event.currentTarget.setPointerCapture(event.pointerId);
                  dispatch({
                    type: "beginMove",
                    index,
                    point: normalizedPoint(event, stageRef.current),
                  });
                }}
              >
                <span style={labelStyle}>{box.className}</span>
                {isSelected
                  ? (["nw", "ne", "sw", "se"] as const).map((handle) => (
                      <span
                        key={handle}
                        style={{
                          ...handleStyle,
                          ...handlePositionStyle(handle),
                        }}
                        onPointerDown={(event) => {
                          if (!stageRef.current) {
                            return;
                          }
                          event.stopPropagation();
                          event.currentTarget.setPointerCapture(
                            event.pointerId,
                          );
                          dispatch({
                            type: "beginResize",
                            handle,
                            index,
                            point: normalizedPoint(event, stageRef.current),
                          });
                        }}
                      />
                    ))
                  : null}
              </span>
            );
          },
        )}
      </section>

      <footer style={footerStyle}>
        <code style={pathStyle}>{initial.imagePath}</code>
        <span>{state.boxes.length} boxes</span>
      </footer>
    </main>
  );

  function save(): void {
    postToExtension({
      type: "saveAnnotation",
      imagePath: initial.imagePath,
      boxes: state.boxes,
    });
    dispatch({ type: "status", status: "Saving labels..." });
  }
}

export function createAnnotationEditorState(
  boxes: DatasetSampleBox[],
  status: string | null = null,
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
  action: AnnotationEditorAction,
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
        boxes: state.boxes.filter(
          (_box, index) => index !== state.selectedIndex,
        ),
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
    case "status":
      return { ...state, status: action.status };
    default:
      return state;
  }
}

function applyPointer(
  state: AnnotationEditorState,
  point: Point,
  finish: boolean,
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
      const nextBox = moveBox(
        state.interaction.origin,
        state.interaction.start,
        point,
      );
      const nextBoxes = replaceBox(
        state.boxes,
        state.interaction.index,
        nextBox,
      );
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
      const nextBox = resizeBox(
        state.interaction.origin,
        state.interaction.handle,
        point,
      );
      const nextBoxes = replaceBox(
        state.boxes,
        state.interaction.index,
        nextBox,
      );
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

function handleKeyDown(
  event: KeyboardEvent<HTMLElement>,
  dispatch: (action: AnnotationEditorAction) => void,
): void {
  if (event.key === "Delete" || event.key === "Backspace") {
    event.preventDefault();
    dispatch({ type: "deleteSelected" });
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
    event.preventDefault();
    dispatch({ type: "undo" });
  }
}

function normalizedPoint(
  event: PointerEvent<HTMLElement>,
  target: HTMLElement,
): Point {
  const rect = target.getBoundingClientRect();
  return {
    x: clamp((event.clientX - rect.left) / rect.width),
    y: clamp((event.clientY - rect.top) / rect.height),
  };
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

function moveBox(
  box: DatasetSampleBox,
  start: Point,
  point: Point,
): DatasetSampleBox {
  const deltaX = point.x - start.x;
  const deltaY = point.y - start.y;
  return {
    ...box,
    x: clamp(box.x + deltaX, 0, 1 - box.width),
    y: clamp(box.y + deltaY, 0, 1 - box.height),
  };
}

function resizeBox(
  box: DatasetSampleBox,
  handle: ResizeHandle,
  point: Point,
): DatasetSampleBox {
  const left = box.x;
  const top = box.y;
  const right = box.x + box.width;
  const bottom = box.y + box.height;
  const nextLeft = handle.includes("w")
    ? clamp(point.x, 0, right - MIN_BOX_SIZE)
    : left;
  const nextRight = handle.includes("e")
    ? clamp(point.x, left + MIN_BOX_SIZE, 1)
    : right;
  const nextTop = handle.includes("n")
    ? clamp(point.y, 0, bottom - MIN_BOX_SIZE)
    : top;
  const nextBottom = handle.includes("s")
    ? clamp(point.y, top + MIN_BOX_SIZE, 1)
    : bottom;
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
  box: DatasetSampleBox,
): DatasetSampleBox[] {
  return boxes.map((current, currentIndex) =>
    currentIndex === index ? box : current,
  );
}

function pushHistory(
  history: DatasetSampleBox[][],
  boxes: DatasetSampleBox[],
): DatasetSampleBox[][] {
  return [...history, boxes].slice(-50);
}

function boxesEqual(
  left: DatasetSampleBox[],
  right: DatasetSampleBox[],
): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function clamp(value: number, min = 0, max = 1): number {
  return Math.max(min, Math.min(max, value));
}

function handlePositionStyle(handle: ResizeHandle): CSSProperties {
  return {
    cursor: `${handle}-resize`,
    left: handle.includes("w") ? "-5px" : undefined,
    right: handle.includes("e") ? "-5px" : undefined,
    top: handle.includes("n") ? "-5px" : undefined,
    bottom: handle.includes("s") ? "-5px" : undefined,
  };
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  boxSizing: "border-box",
  padding: 20,
  display: "grid",
  gridTemplateRows: "auto auto 1fr auto",
  gap: 12,
  background: "var(--vscode-editor-background)",
  color: "var(--vscode-editor-foreground)",
  fontFamily: "var(--vscode-font-family)",
  outline: "none",
};

const toolbarStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  alignItems: "end",
  flexWrap: "wrap",
};

const eyebrowStyle: CSSProperties = {
  margin: "0 0 6px",
  color: "var(--vscode-charts-orange)",
  fontSize: 12,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
};

const titleStyle: CSSProperties = {
  margin: 0,
  fontSize: 26,
  lineHeight: 1.15,
};

const controlsStyle: CSSProperties = {
  display: "flex",
  gap: 8,
  flexWrap: "wrap",
};

const stageStyle: CSSProperties = {
  position: "relative",
  minHeight: 360,
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editorWidget-background)",
  overflow: "hidden",
  cursor: "crosshair",
};

const imageStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "contain",
  display: "block",
  userSelect: "none",
  pointerEvents: "none",
};

const boxStyle: CSSProperties = {
  position: "absolute",
  border: "2px solid var(--vscode-charts-orange)",
  cursor: "move",
};

const selectedBoxStyle: CSSProperties = {
  borderColor: "var(--vscode-charts-blue)",
  boxShadow: "0 0 0 1px var(--vscode-charts-blue)",
};

const labelStyle: CSSProperties = {
  position: "absolute",
  left: 0,
  top: -20,
  padding: "2px 6px",
  background: "var(--vscode-charts-orange)",
  color: "var(--vscode-editor-background)",
  fontSize: 11,
  fontWeight: 700,
  pointerEvents: "none",
};

const handleStyle: CSSProperties = {
  position: "absolute",
  width: 10,
  height: 10,
  border: "1px solid var(--vscode-editor-background)",
  background: "var(--vscode-charts-blue)",
};

const inputStyle: CSSProperties = {
  padding: "8px 10px",
  border: "1px solid var(--vscode-input-border)",
  background: "var(--vscode-input-background)",
  color: "var(--vscode-input-foreground)",
};

const buttonStyle: CSSProperties = {
  padding: "8px 12px",
  border: "1px solid var(--vscode-button-border, var(--vscode-panel-border))",
  background: "var(--vscode-button-background)",
  color: "var(--vscode-button-foreground)",
  cursor: "pointer",
};

const secondaryButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "var(--vscode-editorWidget-background)",
  color: "var(--vscode-editor-foreground)",
};

const statusStyle: CSSProperties = {
  padding: "10px 12px",
  border: "1px solid var(--vscode-inputValidation-infoBorder)",
  background: "var(--vscode-inputValidation-infoBackground)",
};

const footerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  alignItems: "center",
};

const pathStyle: CSSProperties = {
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const rootNode =
  typeof document === "undefined" ? null : document.getElementById("root");
if (rootNode) {
  createRoot(rootNode).render(<AnnotationEditorApp />);
}

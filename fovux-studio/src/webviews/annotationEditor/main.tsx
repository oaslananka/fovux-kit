import { useEffect, useReducer, useRef, useState } from "react";
import type { CSSProperties, JSX, KeyboardEvent, PointerEvent } from "react";
import { createRoot } from "react-dom/client";

import {
  postToExtension,
  readInitialState,
  type AnnotationEditorInitialState,
} from "../shared/types";
import { AnnotationQueueCard, AnnotationToolbar } from "./components/AnnotationControls";
import {
  annotationEditorReducer,
  clamp,
  createAnnotationEditorState,
  type AnnotationEditorAction,
  type Point,
  type ResizeHandle,
} from "./model";

function sanitizeImageUri(uri: unknown): string {
  if (typeof uri !== "string") {
    return "";
  }

  const value = uri.trim();
  if (!value) {
    return "";
  }

  if (value.startsWith("vscode-webview-resource:")) {
    return value;
  }

  if (/^data:image\/[a-zA-Z0-9.+-]+;base64,[a-zA-Z0-9+/=]+$/.test(value)) {
    return value;
  }

  return "";
}

function AnnotationEditorApp(): JSX.Element {
  const [editorState, setEditorState] = useState<AnnotationEditorInitialState>(() =>
    readInitialState<AnnotationEditorInitialState>({
      imagePath: "",
      imageUri: "",
      classNames: ["class_0"],
      initialBoxes: [],
      initialError: "Initial annotation editor state was not provided.",
    })
  );
  const [datasetSplit, setDatasetSplit] = useState<string>("train");
  const stageRef = useRef<HTMLElement | null>(null);
  const [classId, setClassId] = useReducer((_current: number, next: number) => next, 0);
  const [state, dispatch] = useReducer(
    annotationEditorReducer,
    createAnnotationEditorState(editorState.initialBoxes, editorState.initialError)
  );

  useEffect(() => {
    dispatch({
      type: "reset",
      boxes: editorState.initialBoxes,
      status: editorState.initialError,
    });
  }, [editorState]);

  useEffect(() => {
    const listener = (event: MessageEvent) => {
      const message = event.data;
      if (!message || message.type !== "setEditorState" || !message.state) {
        return;
      }

      const nextState = message.state as AnnotationEditorInitialState;
      setEditorState({
        ...nextState,
        imageUri: sanitizeImageUri(nextState.imageUri),
      });
    };
    window.addEventListener("message", listener);
    return () => window.removeEventListener("message", listener);
  }, []);

  return (
    <main style={pageStyle} tabIndex={0} onKeyDown={(event) => handleKeyDown(event, dispatch)}>
      <AnnotationToolbar
        isQueueMode={editorState.isQueueMode === true}
        classNames={editorState.classNames}
        classId={classId}
        onClassIdChange={setClassId}
        onSave={save}
        onSubmitQueue={submitQueue}
        onSkipQueue={skipQueue}
        onUndo={() => dispatch({ type: "undo" })}
        onClear={() => dispatch({ type: "clear" })}
      />

      {editorState.isQueueMode ? (
        <AnnotationQueueCard
          queueScore={editorState.queueScore}
          queueReason={editorState.queueReason}
          datasetSplit={datasetSplit}
          onDatasetSplitChange={setDatasetSplit}
        />
      ) : null}

      {state.status ? <p style={statusStyle}>{state.status}</p> : null}

      <section
        ref={stageRef}
        style={stageStyle}
        onPointerDown={(event) => {
          event.currentTarget.focus();
          event.currentTarget.setPointerCapture(event.pointerId);
          const point = normalizedPoint(event, event.currentTarget);
          const className = editorState.classNames[classId] ?? `class_${classId}`;
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
          src={editorState.imageUri}
          alt={editorState.imagePath}
          style={imageStyle}
          draggable={false}
        />
        {[...state.boxes, ...(state.draft ? [state.draft] : [])].map((box, index) => {
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
                        event.currentTarget.setPointerCapture(event.pointerId);
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
        })}
      </section>

      <footer style={footerStyle}>
        <code style={pathStyle}>{editorState.imagePath}</code>
        <span>{state.boxes.length} boxes</span>
      </footer>
    </main>
  );

  function save(): void {
    postToExtension({
      type: "saveAnnotation",
      imagePath: editorState.imagePath,
      boxes: state.boxes,
    });
    dispatch({ type: "status", status: "Saving labels..." });
  }

  function submitQueue(): void {
    if (editorState.queueEntryId) {
      postToExtension({
        type: "submitQueueEntry",
        entryId: editorState.queueEntryId,
        boxes: state.boxes,
        datasetSplit,
      });
      dispatch({ type: "status", status: "Submitting corrections..." });
    }
  }

  function skipQueue(): void {
    if (editorState.queueEntryId) {
      postToExtension({
        type: "skipQueueEntry",
        entryId: editorState.queueEntryId,
      });
      dispatch({ type: "status", status: "Skipping queue item..." });
    }
  }
}

function handleKeyDown(
  event: KeyboardEvent<HTMLElement>,
  dispatch: (action: AnnotationEditorAction) => void
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

function normalizedPoint(event: PointerEvent<HTMLElement>, target: HTMLElement): Point {
  const rect = target.getBoundingClientRect();
  return {
    x: clamp((event.clientX - rect.left) / rect.width),
    y: clamp((event.clientY - rect.top) / rect.height),
  };
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

const rootNode = typeof document === "undefined" ? null : document.getElementById("root");
if (rootNode) {
  createRoot(rootNode).render(<AnnotationEditorApp />);
}

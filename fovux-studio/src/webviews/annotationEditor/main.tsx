import { useEffect, useReducer, useRef, useState } from "react";
import type { CSSProperties, JSX, KeyboardEvent } from "react";
import { createRoot } from "react-dom/client";

import {
  postToExtension,
  readInitialState,
  type AnnotationEditorInitialState,
} from "../shared/types";
import { AnnotationCanvas } from "./components/AnnotationCanvas";
import { AnnotationQueueCard, AnnotationToolbar } from "./components/AnnotationControls";
import { createAnnotationPointerController } from "./controller";
import { sanitizeAnnotationEditorState } from "./imageUri";
import {
  annotationEditorReducer,
  createAnnotationEditorState,
  type AnnotationEditorAction,
} from "./model";

function AnnotationEditorApp(): JSX.Element {
  const [editorState, setEditorState] = useState<AnnotationEditorInitialState>(() =>
    sanitizeAnnotationEditorState(
      readInitialState<AnnotationEditorInitialState>({
        imagePath: "",
        imageUri: "",
        classNames: ["class_0"],
        initialBoxes: [],
        initialError: "Initial annotation editor state was not provided.",
      })
    )
  );
  const [datasetSplit, setDatasetSplit] = useState<string>("train");
  const stageRef = useRef<HTMLElement | null>(null);
  const [classId, setClassId] = useReducer((_current: number, next: number) => next, 0);
  const [state, dispatch] = useReducer(
    annotationEditorReducer,
    createAnnotationEditorState(editorState.initialBoxes, editorState.initialError)
  );
  const pointerController = createAnnotationPointerController({
    stageRef,
    classNames: editorState.classNames,
    classId,
    dispatch,
  });

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
      setEditorState(sanitizeAnnotationEditorState(nextState));
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

      <AnnotationCanvas
        stageRef={stageRef}
        imageUri={editorState.imageUri}
        imagePath={editorState.imagePath}
        boxes={state.boxes}
        draft={state.draft}
        selectedIndex={state.selectedIndex}
        {...pointerController}
      />

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

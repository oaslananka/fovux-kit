import type { CSSProperties, JSX, PointerEvent, PointerEventHandler, RefObject } from "react";

import type { DatasetSampleBox } from "../../shared/types";
import { sanitizeAnnotationImageUri } from "../imageUri";
import type { ResizeHandle } from "../model";

interface AnnotationCanvasProps {
  stageRef: RefObject<HTMLElement | null>;
  imageUri: string;
  imagePath: string;
  boxes: DatasetSampleBox[];
  draft: DatasetSampleBox | null;
  selectedIndex: number | null;
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

const RESIZE_HANDLES: ResizeHandle[] = ["nw", "ne", "sw", "se"];

export function AnnotationCanvas({
  stageRef,
  imageUri,
  imagePath,
  boxes,
  draft,
  selectedIndex,
  onStagePointerDown,
  onStagePointerMove,
  onStagePointerUp,
  onStagePointerCancel,
  onBoxPointerDown,
  onResizePointerDown,
}: Readonly<AnnotationCanvasProps>): JSX.Element {
  const overlays = [...boxes, ...(draft ? [draft] : [])];
  const safeImageUri = sanitizeAnnotationImageUri(imageUri);
  const imageBackgroundStyle: CSSProperties = safeImageUri
    ? { ...imageStyle, backgroundImage: `url(${JSON.stringify(safeImageUri)})` }
    : imageStyle;
  return (
    <section
      ref={stageRef}
      style={stageStyle}
      onPointerDown={onStagePointerDown}
      onPointerMove={onStagePointerMove}
      onPointerUp={onStagePointerUp}
      onPointerCancel={onStagePointerCancel}
    >
      <div role="img" aria-label={imagePath} style={imageBackgroundStyle} />
      {overlays.map((box, index) => {
        const isDraft = index >= boxes.length;
        const isSelected = selectedIndex === index && !isDraft;
        return (
          <span
            key={`${box.classId}-${box.x}-${box.y}-${index}`}
            style={{
              ...boxStyle,
              ...(isSelected ? selectedBoxStyle : {}),
              left: `${box.x * 100}%`,
              top: `${box.y * 100}%`,
              width: `${box.width * 100}%`,
              height: `${box.height * 100}%`,
            }}
            onPointerDown={(event) => onBoxPointerDown(index, event)}
          >
            <span style={labelStyle}>{box.className}</span>
            {isSelected
              ? RESIZE_HANDLES.map((handle) => (
                  <span
                    key={handle}
                    style={{ ...handleStyle, ...handlePositionStyle(handle) }}
                    onPointerDown={(event) => onResizePointerDown(handle, index, event)}
                  />
                ))
              : null}
          </span>
        );
      })}
    </section>
  );
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

const stageStyle: CSSProperties = {
  position: "relative",
  minHeight: 360,
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-editorWidget-background)",
  overflow: "hidden",
  cursor: "crosshair",
};

const imageStyle: CSSProperties = {
  position: "absolute",
  inset: 0,
  backgroundPosition: "center",
  backgroundRepeat: "no-repeat",
  backgroundSize: "contain",
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

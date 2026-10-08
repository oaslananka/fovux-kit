import { isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { AnnotationCanvas } from "../../src/webviews/annotationEditor/components/AnnotationCanvas";
import type { DatasetSampleBox } from "../../src/webviews/shared/types";

const BOX: DatasetSampleBox = {
  classId: 0,
  className: "cat",
  x: 0.1,
  y: 0.2,
  width: 0.3,
  height: 0.4,
};

describe("annotation canvas", () => {
  it("renders the image, boxes, selected resize handles, and draft overlay", () => {
    const markup = renderToStaticMarkup(
      <AnnotationCanvas
        stageRef={{ current: null }}
        imageUri="data:image/png;base64,AAAA"
        imagePath="/data/cat.png"
        boxes={[BOX]}
        draft={{ ...BOX, className: "draft", x: 0.5 }}
        selectedIndex={0}
        onStagePointerDown={vi.fn()}
        onStagePointerMove={vi.fn()}
        onStagePointerUp={vi.fn()}
        onStagePointerCancel={vi.fn()}
        onBoxPointerDown={vi.fn()}
        onResizePointerDown={vi.fn()}
      />
    );

    expect(markup).toContain('role="img"');
    expect(markup).toContain('aria-label="/data/cat.png"');
    expect(markup).toContain("background-image");
    expect(markup).not.toContain("<img");
    expect(markup).toContain("cat");
    expect(markup).toContain("draft");
    expect(markup.match(/-resize/g)).toHaveLength(4);
  });

  it("omits the image background when the resource URI is rejected", () => {
    const markup = renderToStaticMarkup(
      <AnnotationCanvas
        stageRef={{ current: null }}
        imageUri="https://example.com/cat.png"
        imagePath="/data/cat.png"
        boxes={[]}
        draft={null}
        selectedIndex={null}
        onStagePointerDown={vi.fn()}
        onStagePointerMove={vi.fn()}
        onStagePointerUp={vi.fn()}
        onStagePointerCancel={vi.fn()}
        onBoxPointerDown={vi.fn()}
        onResizePointerDown={vi.fn()}
      />
    );

    expect(markup).toContain('role="img"');
    expect(markup).not.toContain("background-image");
  });

  it("forwards stage, box, and resize pointer events to controller callbacks", () => {
    const onStagePointerDown = vi.fn();
    const onStagePointerMove = vi.fn();
    const onStagePointerUp = vi.fn();
    const onStagePointerCancel = vi.fn();
    const onBoxPointerDown = vi.fn();
    const onResizePointerDown = vi.fn();
    const tree = AnnotationCanvas({
      stageRef: { current: null },
      imageUri: "data:image/png;base64,AAAA",
      imagePath: "/data/cat.png",
      boxes: [BOX],
      draft: null,
      selectedIndex: 0,
      onStagePointerDown,
      onStagePointerMove,
      onStagePointerUp,
      onStagePointerCancel,
      onBoxPointerDown,
      onResizePointerDown,
    });
    const stage = requireElement(tree, (element) => element.type === "section", "annotation stage");
    const pointerEvent = {} as never;

    (stage.props as { onPointerDown: (event: never) => void }).onPointerDown(pointerEvent);
    (stage.props as { onPointerMove: (event: never) => void }).onPointerMove(pointerEvent);
    (stage.props as { onPointerUp: (event: never) => void }).onPointerUp(pointerEvent);
    (stage.props as { onPointerCancel: (event: never) => void }).onPointerCancel(pointerEvent);
    expect(onStagePointerDown).toHaveBeenCalledWith(pointerEvent);
    expect(onStagePointerMove).toHaveBeenCalledWith(pointerEvent);
    expect(onStagePointerUp).toHaveBeenCalledWith(pointerEvent);
    expect(onStagePointerCancel).toHaveBeenCalledWith(pointerEvent);

    const movable = requireElement(
      tree,
      (element) => {
        const props = element.props as { style?: { cursor?: string }; onPointerDown?: unknown };
        return props.style?.cursor === "move" && typeof props.onPointerDown === "function";
      },
      "movable annotation box"
    );
    (movable.props as { onPointerDown: (event: never) => void }).onPointerDown(pointerEvent);
    expect(onBoxPointerDown).toHaveBeenCalledWith(0, pointerEvent);

    const resize = requireElement(
      tree,
      (element) => {
        const props = element.props as { style?: { cursor?: string }; onPointerDown?: unknown };
        return props.style?.cursor === "nw-resize" && typeof props.onPointerDown === "function";
      },
      "north-west resize handle"
    );
    (resize.props as { onPointerDown: (event: never) => void }).onPointerDown(pointerEvent);
    expect(onResizePointerDown).toHaveBeenCalledWith("nw", 0, pointerEvent);
  });
});

function requireElement(
  node: ReactNode,
  predicate: (element: ReactElement) => boolean,
  description: string
): ReactElement {
  const match = findElement(node, predicate);
  if (!match) {
    throw new Error(`Missing ${description}`);
  }
  return match;
}

function findElement(
  node: ReactNode,
  predicate: (element: ReactElement) => boolean
): ReactElement | null {
  if (Array.isArray(node)) {
    for (const child of node) {
      const match = findElement(child, predicate);
      if (match) return match;
    }
    return null;
  }
  if (!isValidElement(node)) return null;
  if (predicate(node)) return node;
  const children = (node.props as { children?: ReactNode }).children;
  for (const child of Array.isArray(children) ? children : [children]) {
    const match = findElement(child, predicate);
    if (match) return match;
  }
  return null;
}

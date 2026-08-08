import { isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  AnnotationQueueCard,
  AnnotationToolbar,
} from "../../src/webviews/annotationEditor/components/AnnotationControls";

describe("annotation editor controls", () => {
  it("renders accessible standard editor actions", () => {
    const html = renderToStaticMarkup(
      <AnnotationToolbar
        isQueueMode={false}
        classNames={["cat", "dog"]}
        classId={1}
        onClassIdChange={vi.fn()}
        onSave={vi.fn()}
        onSubmitQueue={vi.fn()}
        onSkipQueue={vi.fn()}
        onUndo={vi.fn()}
        onClear={vi.fn()}
      />
    );

    expect(html).toContain('aria-label="Class label"');
    expect(html).toContain("Save labels");
    expect(html).toContain("Undo");
    expect(html).toContain("Clear");
    expect(html).not.toContain("Submit corrections");
  });

  it("renders queue actions and accessible split metadata", () => {
    const toolbar = renderToStaticMarkup(
      <AnnotationToolbar
        isQueueMode
        classNames={["cat"]}
        classId={0}
        onClassIdChange={vi.fn()}
        onSave={vi.fn()}
        onSubmitQueue={vi.fn()}
        onSkipQueue={vi.fn()}
        onUndo={vi.fn()}
        onClear={vi.fn()}
      />
    );
    const queueCard = renderToStaticMarkup(
      <AnnotationQueueCard
        queueScore={0.81234}
        queueReason="low confidence"
        datasetSplit="val"
        onDatasetSplitChange={vi.fn()}
      />
    );

    expect(toolbar).toContain("Submit corrections");
    expect(toolbar).toContain("Skip item");
    expect(toolbar).not.toContain("Save labels");
    expect(queueCard).toContain("0.8123");
    expect(queueCard).toContain("low confidence");
    expect(queueCard).toContain('aria-label="Dataset split"');
  });
  it("forwards class and dataset split selections to typed callbacks", () => {
    const onClassIdChange = vi.fn();
    const toolbar = AnnotationToolbar({
      isQueueMode: false,
      classNames: ["cat", "dog"],
      classId: 0,
      onClassIdChange,
      onSave: vi.fn(),
      onSubmitQueue: vi.fn(),
      onSkipQueue: vi.fn(),
      onUndo: vi.fn(),
      onClear: vi.fn(),
    });
    const classSelect = findElementByAriaLabel(toolbar, "Class label");
    const classOnChange = (classSelect.props as { onChange: (event: { target: { value: string } }) => void }).onChange;
    classOnChange({ target: { value: "1" } });
    expect(onClassIdChange).toHaveBeenCalledWith(1);

    const onDatasetSplitChange = vi.fn();
    const queueCard = AnnotationQueueCard({
      datasetSplit: "train",
      onDatasetSplitChange,
    });
    const splitSelect = findElementByAriaLabel(queueCard, "Dataset split");
    const splitOnChange = (splitSelect.props as { onChange: (event: { target: { value: string } }) => void }).onChange;
    splitOnChange({ target: { value: "test" } });
    expect(onDatasetSplitChange).toHaveBeenCalledWith("test");

    const fallbackMarkup = renderToStaticMarkup(queueCard);
    expect(fallbackMarkup.match(/N\/A/g)).toHaveLength(2);
  });

});

function findElementByAriaLabel(root: ReactElement, label: string): ReactElement {
  const match = findElement(root, (element) =>
    (element.props as { "aria-label"?: string })["aria-label"] === label
  );
  if (!match) {
    throw new Error(`Missing element with aria-label ${label}`);
  }
  return match;
}

function findElement(
  node: ReactNode,
  predicate: (element: ReactElement) => boolean
): ReactElement | null {
  if (!isValidElement(node)) {
    return null;
  }
  if (predicate(node)) {
    return node;
  }
  const children = (node.props as { children?: ReactNode }).children;
  for (const child of Array.isArray(children) ? children : [children]) {
    const match = findElement(child, predicate);
    if (match) {
      return match;
    }
  }
  return null;
}

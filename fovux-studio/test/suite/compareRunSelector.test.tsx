import { isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { CompareRunSelector } from "../../src/webviews/compareRuns/components/CompareRunSelector";
import type { RunSummary } from "../../src/webviews/shared/api";

const RUNS: RunSummary[] = [
  {
    id: "run-a",
    status: "completed",
    model: "a.pt",
    epochs: 10,
    created_at: null,
  },
  {
    id: "run-b",
    status: "running",
    model: "b.pt",
    epochs: 20,
    created_at: null,
  },
];

describe("compare run selector", () => {
  it("renders the empty state when no runs are available", () => {
    const markup = renderToStaticMarkup(
      <CompareRunSelector runs={[]} selectedRunIds={[]} onToggleRun={vi.fn()} />
    );

    expect(markup).toContain("No runs available yet");
  });

  it("renders selected runs and forwards checkbox changes", () => {
    const onToggleRun = vi.fn();
    const tree = CompareRunSelector({
      runs: RUNS,
      selectedRunIds: ["run-a"],
      onToggleRun,
    });
    const markup = renderToStaticMarkup(tree);

    expect(markup).toContain("run-a");
    expect(markup).toContain("run-b");
    expect(markup).toContain("checked");

    const runBInput = requireElement(
      tree,
      (element) => {
        const props = element.props as { type?: string; checked?: boolean; onChange?: unknown };
        return props.type === "checkbox" && props.checked === false && typeof props.onChange === "function";
      },
      "run-b checkbox"
    );
    (runBInput.props as { onChange: () => void }).onChange();
    expect(onToggleRun).toHaveBeenCalledWith("run-b");
  });
});

function requireElement(
  node: ReactNode,
  predicate: (element: ReactElement) => boolean,
  description: string
): ReactElement {
  const match = findElement(node, predicate);
  if (!match) throw new Error(`Missing ${description}`);
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

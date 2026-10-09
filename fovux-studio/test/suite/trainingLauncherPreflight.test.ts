import { isValidElement, type ReactElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  invokeTool: vi.fn(),
  setValues: [] as unknown[],
}));

vi.mock("react", async (importOriginal) => {
  const original = await importOriginal<typeof import("react")>();
  return {
    ...original,
    useState: (initial: unknown) => [
      typeof initial === "function" ? (initial as () => unknown)() : initial,
      (value: unknown) => mocks.setValues.push(value),
    ],
    useEffect: () => {},
    useMemo: (compute: () => unknown) => compute(),
  };
});

vi.mock("../../src/webviews/shared/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../src/webviews/shared/api")>()),
  invokeTool: mocks.invokeTool,
}));

vi.mock("../../src/webviews/shared/types", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../src/webviews/shared/types")>()),
  readInitialState: (fallback: Record<string, unknown>) => ({
    ...fallback,
    initialDatasetPath: "/tmp/test-dataset",
    initialError: null,
    isServerReachable: true,
  }),
}));

import { TrainingLauncherApp } from "../../src/webviews/trainingLauncher/main";

function findStartButton(node: ReactNode): ReactElement | null {
  if (!isValidElement(node)) return null;
  const props = node.props as { children?: ReactNode; onClick?: () => void };
  if (node.type === "button" && props.children === "Start training") return node;
  for (const child of Array.isArray(props.children) ? props.children : [props.children]) {
    const result = findStartButton(child);
    if (result) return result;
  }
  return null;
}

describe("training launcher preflight blockers", () => {
  beforeEach(() => {
    mocks.invokeTool.mockReset();
    mocks.setValues.length = 0;
    vi.stubGlobal("window", {
      localStorage: { getItem: () => null },
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
  });

  it.each([
    { blockers: ["incompatible checkpoint", 42], expected: ["- incompatible checkpoint", "- 42"] },
    { blockers: "invalid server data", expected: ["Training preflight blocked launch."] },
  ])("blocks unapproved launches for blockers=$blockers", async ({ blockers, expected }) => {
    mocks.invokeTool.mockResolvedValue({ ready: false, blockers, next_actions: ["Fix input"] });
    const start = findStartButton(TrainingLauncherApp());
    expect(start).not.toBeNull();
    (start?.props as { onClick: () => void }).onClick();

    await vi.waitFor(() => {
      expect(mocks.invokeTool).toHaveBeenCalledOnce();
      expect(mocks.invokeTool).toHaveBeenCalledWith(
        expect.anything(),
        "train_preflight",
        expect.objectContaining({ dataset_path: "/tmp/test-dataset" })
      );
      const error = mocks.setValues.find(
        (value) => typeof value === "string" && value.includes("Training preflight blocked launch.")
      ) as string | undefined;
      expect(error).toBeDefined();
      for (const message of expected) expect(error).toContain(message);
      expect(error).toContain("Next: Fix input");
    });
  });
});

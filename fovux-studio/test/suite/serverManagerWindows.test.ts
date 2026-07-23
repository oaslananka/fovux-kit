import type { ChildProcessWithoutNullStreams } from "node:child_process";
import { afterEach, describe, expect, it, vi } from "vitest";

import "./helpers/vscodeMock";

const { execFileMock } = vi.hoisted(() => ({ execFileMock: vi.fn() }));

vi.mock("node:child_process", async (importOriginal) => {
  const actual = await importOriginal<typeof import("node:child_process")>();
  return { ...actual, execFile: execFileMock };
});

import {
  killProcessTree,
  WINDOWS_TASKKILL_EXECUTABLE,
} from "../../src/fovux/serverManager";

describe("killProcessTree", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    execFileMock.mockReset();
  });

  it("uses the fixed system taskkill executable on Windows", () => {
    vi.spyOn(process, "platform", "get").mockReturnValue("win32");
    const fallbackKill = vi.fn();
    const child = { pid: 4242, kill: fallbackKill } as unknown as ChildProcessWithoutNullStreams;

    killProcessTree(child);

    expect(execFileMock).toHaveBeenCalledWith(
      WINDOWS_TASKKILL_EXECUTABLE,
      ["/PID", "4242", "/T", "/F"],
      expect.any(Function)
    );
    const callback = execFileMock.mock.calls[0]?.[2];
    expect(callback).toBeTypeOf("function");
    callback?.(null);
    expect(fallbackKill).not.toHaveBeenCalled();
  });

  it("falls back to the child process kill method when taskkill fails", () => {
    vi.spyOn(process, "platform", "get").mockReturnValue("win32");
    const fallbackKill = vi.fn();
    const child = { pid: 4242, kill: fallbackKill } as unknown as ChildProcessWithoutNullStreams;

    killProcessTree(child);
    const callback = execFileMock.mock.calls[0]?.[2];
    callback?.(new Error("taskkill failed"));

    expect(fallbackKill).toHaveBeenCalledOnce();
  });
});

import { EventEmitter } from "node:events";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { resetVscodeMockState, setWorkspaceTrust } from "./helpers/vscodeMock";
import "./helpers/vscodeMock";

describe("startFovuxServer", () => {
  beforeEach(() => {
    resetVscodeMockState();
    vi.resetModules();
  });

  it("uses the fixed Windows system taskkill executable", async () => {
    const { WINDOWS_TASKKILL_EXECUTABLE } = await import("../../src/fovux/serverManager");

    expect(WINDOWS_TASKKILL_EXECUTABLE).toBe("C:\\Windows\\System32\\taskkill.exe");
  });

  it("throws in an untrusted workspace before probing the server", async () => {
    setWorkspaceTrust(false);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { startFovuxServer } = await import("../../src/fovux/serverManager");

    await expect(startFovuxServer()).rejects.toThrow(/untrusted workspace/i);
    expect(fetchMock).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("stops a spawned server when readiness times out", async () => {
    vi.useFakeTimers();
    const proc = Object.assign(new EventEmitter(), {
      pid: 123456,
      stdout: new EventEmitter(),
      stderr: new EventEmitter(),
      kill: vi.fn(),
    });
    const spawn = vi.fn(() => proc);
    vi.doMock("node:child_process", () => ({ spawn, execFile: vi.fn() }));
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    try {
      const { startFovuxServer } = await import("../../src/fovux/serverManager");
      const starting = startFovuxServer();
      const failure = expect(starting).rejects.toThrow(/did not become healthy/i);
      await vi.advanceTimersByTimeAsync(15_100);
      await failure;
      expect(spawn).toHaveBeenCalledOnce();
      expect(proc.kill).toHaveBeenCalledOnce();
    } finally {
      vi.useRealTimers();
      vi.doUnmock("node:child_process");
      vi.unstubAllGlobals();
    }
  });

  it("shows an information message when the server is already running", async () => {
    const fovuxHome = await mkdtemp(join(tmpdir(), "fovux-server-manager-"));
    vi.stubEnv("FOVUX_HOME", fovuxHome);
    await writeFile(join(fovuxHome, "auth.token"), "test-token", "utf8");
    const vscode = await import("vscode");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    try {
      const { startFovuxServer } = await import("../../src/fovux/serverManager");

      await startFovuxServer();

      expect(vscode.window.showInformationMessage).toHaveBeenCalledWith(
        "Fovux server is already running."
      );
    } finally {
      vi.unstubAllGlobals();
      vi.unstubAllEnvs();
      await rm(fovuxHome, { recursive: true, force: true });
    }
  });
});

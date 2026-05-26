import { beforeEach, describe, expect, it, vi } from "vitest";

import { resetVscodeMockState, setWorkspaceTrust } from "./helpers/vscodeMock";
import "./helpers/vscodeMock";

describe("startFovuxServer", () => {
  beforeEach(() => {
    resetVscodeMockState();
    vi.resetModules();
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

  it("shows an information message when the server is already running", async () => {
    const vscode = await import("vscode");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    const { startFovuxServer } = await import("../../src/fovux/serverManager");

    await startFovuxServer();

    expect(vscode.window.showInformationMessage).toHaveBeenCalledWith(
      "Fovux server is already running.",
    );
    vi.unstubAllGlobals();
  });
});

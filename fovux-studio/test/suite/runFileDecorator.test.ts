import * as path from "node:path";

import { describe, expect, it } from "vitest";

import "./helpers/vscodeMock";
import * as vscode from "vscode";

import { RunFileDecorationProvider } from "../../src/decorations/runFileDecorator";

describe("RunFileDecorationProvider", () => {
  it("decorates completed and failed run folders", () => {
    const provider = new RunFileDecorationProvider();
    const completePath = path.join("fovux-home", "runs", "run_complete");
    const failedPath = path.join("fovux-home", "runs", "run_failed");

    provider.update([
      { runPath: completePath, status: "completed" },
      { runPath: failedPath, status: "failed" },
    ]);

    expect(
      provider.provideFileDecoration(vscode.Uri.file(completePath))?.tooltip,
    ).toBe("Fovux run: completed");
    expect(
      provider.provideFileDecoration(vscode.Uri.file(failedPath))?.tooltip,
    ).toBe("Fovux run: failed");
    expect(
      provider.provideFileDecoration(vscode.Uri.file("other")),
    ).toBeUndefined();
  });
});

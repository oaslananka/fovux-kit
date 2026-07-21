import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { runInstalledExtensionAssertions } from "./installedExtension.test";

const SCROT_EXECUTABLE = "/usr/bin/scrot";

export async function run(): Promise<void> {
  const mode = process.env["FOVUX_E2E_MODE"] ?? "unknown";
  const artifacts = process.env["FOVUX_E2E_ARTIFACTS"];
  if (!artifacts) {
    throw new Error("FOVUX_E2E_ARTIFACTS is required");
  }
  mkdirSync(artifacts, { recursive: true });

  try {
    const tests = await runInstalledExtensionAssertions();
    const passed = tests.filter((test) => test.status === "passed").length;
    const skipped = tests.filter((test) => test.status === "skipped").length;
    writeResult(artifacts, {
      mode,
      failures: 0,
      passed,
      skipped,
      successful: true,
      tests,
      completedAt: new Date().toISOString(),
    });
  } catch (error) {
    const message = error instanceof Error ? (error.stack ?? error.message) : String(error);
    writeResult(artifacts, {
      mode,
      failures: 1,
      passed: 0,
      skipped: 0,
      successful: false,
      error: message,
      completedAt: new Date().toISOString(),
    });
    captureFailureScreenshot(artifacts, mode);
    throw error;
  }
}

function writeResult(artifacts: string, result: object): void {
  writeFileSync(join(artifacts, "result.json"), `${JSON.stringify(result, null, 2)}\n`, "utf8");
}

function captureFailureScreenshot(artifacts: string, mode: string): void {
  const result = spawnSync(SCROT_EXECUTABLE, [join(artifacts, `${mode}-failure.png`)], {
    encoding: "utf8",
  });
  if (result.status !== 0) {
    writeFileSync(
      join(artifacts, "screenshot-error.log"),
      `${result.stderr || result.stdout || "scrot was unavailable"}\n`,
      "utf8"
    );
  }
}

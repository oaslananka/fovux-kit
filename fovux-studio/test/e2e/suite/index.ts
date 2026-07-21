import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import Mocha from "mocha";

export async function run(): Promise<void> {
  const mode = process.env["FOVUX_E2E_MODE"] ?? "unknown";
  const artifacts = process.env["FOVUX_E2E_ARTIFACTS"];
  if (!artifacts) {
    throw new Error("FOVUX_E2E_ARTIFACTS is required");
  }
  mkdirSync(artifacts, { recursive: true });

  const mocha = new Mocha({
    ui: "tdd",
    color: true,
    timeout: 30_000,
  });
  mocha.addFile(join(__dirname, "installedExtension.test.js"));

  const failures = await new Promise<number>((resolve) => {
    mocha.run(resolve);
  });
  const result = {
    mode,
    failures,
    passed: failures === 0,
    completedAt: new Date().toISOString(),
  };
  writeFileSync(join(artifacts, "result.json"), `${JSON.stringify(result, null, 2)}\n`, "utf8");

  if (failures > 0) {
    captureFailureScreenshot(artifacts, mode);
    throw new Error(`${failures} Fovux Studio ${mode} E2E test(s) failed`);
  }
}

function captureFailureScreenshot(artifacts: string, mode: string): void {
  const result = spawnSync("scrot", [join(artifacts, `${mode}-failure.png`)], {
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

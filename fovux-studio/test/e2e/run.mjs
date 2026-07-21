import { spawn, spawnSync } from "node:child_process";
import { createWriteStream } from "node:fs";
import { mkdir, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  downloadAndUnzipVSCode,
  resolveCliArgsFromVSCodeExecutablePath,
} from "@vscode/test-electron";

const VSCODE_VERSION = "1.129.1";
const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const studioRoot = resolve(scriptDirectory, "../..");
const repositoryRoot = resolve(studioRoot, "..");
const artifactsRoot = resolve(
  process.env.FOVUX_E2E_ARTIFACTS ?? join(studioRoot, "artifacts", "studio-e2e")
);
const vscodeCache = resolve(
  process.env.FOVUX_E2E_VSCODE_CACHE ?? join(repositoryRoot, ".vscode-test")
);
const vsixPath = join(studioRoot, "fovuxstudiokit.vsix");
const harnessPath = join(scriptDirectory, "harness");
const testsPath = join(scriptDirectory, "out", "suite", "index.js");

await mkdir(artifactsRoot, { recursive: true });

const vscodeExecutablePath = await downloadAndUnzipVSCode({
  version: VSCODE_VERSION,
  cachePath: vscodeCache,
});

for (const scenario of [
  {
    mode: "trusted",
    workspace: join(scriptDirectory, "fixtures", "trusted.code-workspace"),
    launchArgs: ["--disable-workspace-trust"],
  },
  {
    mode: "untrusted",
    workspace: join(scriptDirectory, "fixtures", "untrusted"),
    launchArgs: [],
  },
]) {
  await runScenario(vscodeExecutablePath, scenario);
}

async function runScenario(vscodePath, scenario) {
  const scenarioRoot = join(artifactsRoot, scenario.mode);
  const extensionsDirectory = join(scenarioRoot, "extensions");
  const userDataDirectory = join(scenarioRoot, "user-data");
  const fovuxHome = join(scenarioRoot, "fovux-home");
  const logPath = join(scenarioRoot, "extension-host.log");

  await rm(scenarioRoot, { recursive: true, force: true });
  await mkdir(extensionsDirectory, { recursive: true });
  await mkdir(userDataDirectory, { recursive: true });
  await mkdir(fovuxHome, { recursive: true });

  const cli = resolveCliArgsFromVSCodeExecutablePath(vscodePath);
  const install = spawnSync(
    cli[0],
    [
      ...cli.slice(1),
      "--install-extension",
      vsixPath,
      "--force",
      "--extensions-dir",
      extensionsDirectory,
      "--user-data-dir",
      userDataDirectory,
      "--disable-telemetry",
    ],
    {
      cwd: studioRoot,
      encoding: "utf8",
      env: { ...process.env, FOVUX_HOME: fovuxHome },
    }
  );
  if (install.status !== 0) {
    throw new Error(
      `VSIX installation failed for ${scenario.mode}: ${install.stderr || install.stdout}`
    );
  }

  const installedExtensionPath = await findInstalledExtension(extensionsDirectory);
  const logStream = createWriteStream(logPath, { flags: "w" });
  try {
    await launchExtensionTests(
      vscodePath,
      [
        scenario.workspace,
        "--no-sandbox",
        "--disable-gpu-sandbox",
        "--disable-updates",
        "--skip-welcome",
        "--skip-release-notes",
        `--extensionDevelopmentPath=${harnessPath}`,
        `--extensionTestsPath=${testsPath}`,
        "--extensions-dir",
        extensionsDirectory,
        "--user-data-dir",
        userDataDirectory,
        "--disable-telemetry",
        ...scenario.launchArgs,
      ],
      {
        ...process.env,
        FOVUX_E2E_MODE: scenario.mode,
        FOVUX_E2E_ARTIFACTS: scenarioRoot,
        FOVUX_E2E_EXTENSION_PATH: installedExtensionPath,
        FOVUX_HOME: fovuxHome,
      },
      logStream
    );
  } catch (error) {
    const message = error instanceof Error ? (error.stack ?? error.message) : String(error);
    await writeFile(
      join(scenarioRoot, "runner-failure.json"),
      `${JSON.stringify({ mode: scenario.mode, error: message }, null, 2)}\n`,
      "utf8"
    );
    await captureRunnerFailureScreenshot(scenarioRoot, scenario.mode);
    throw error;
  } finally {
    await new Promise((resolveClose) => logStream.end(resolveClose));
  }
}

async function launchExtensionTests(executable, args, environment, logStream) {
  await new Promise((resolveLaunch, rejectLaunch) => {
    const child = spawn(executable, args, {
      cwd: studioRoot,
      env: environment,
      stdio: ["ignore", "pipe", "pipe"],
    });
    child.stdout.on("data", (chunk) => {
      logStream.write(chunk);
      process.stdout.write(chunk);
    });
    child.stderr.on("data", (chunk) => {
      logStream.write(chunk);
      process.stderr.write(chunk);
    });
    child.once("error", rejectLaunch);
    child.once("close", (code, signal) => {
      if (code === 0) {
        resolveLaunch();
        return;
      }
      rejectLaunch(
        new Error(`VS Code E2E process failed with ${signal ? `signal ${signal}` : `code ${code}`}`)
      );
    });
  });
}

async function captureRunnerFailureScreenshot(scenarioRoot, mode) {
  const screenshot = spawnSync("scrot", [join(scenarioRoot, `${mode}-runner-failure.png`)], {
    encoding: "utf8",
  });
  if (screenshot.status !== 0) {
    const detail = screenshot.stderr || screenshot.stdout || "scrot was unavailable";
    await writeFile(join(scenarioRoot, "runner-screenshot-error.log"), `${detail}\n`, "utf8");
  }
}

async function findInstalledExtension(extensionsDirectory) {
  const entries = await readdir(extensionsDirectory, { withFileTypes: true });
  const matches = entries
    .filter(
      (entry) =>
        entry.isDirectory() && entry.name.toLowerCase().startsWith("oaslananka.fovuxstudiokit-")
    )
    .map((entry) => join(extensionsDirectory, entry.name));
  if (matches.length !== 1) {
    throw new Error(
      `Expected one installed Fovux Studio extension in ${extensionsDirectory}, found ${matches.length}`
    );
  }
  return matches[0];
}

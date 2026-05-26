import {
  execFile,
  spawn,
  type ChildProcessWithoutNullStreams,
} from "node:child_process";
import * as path from "node:path";
import * as vscode from "vscode";

import { getAuthToken, getFovuxBaseUrl } from "./extensionClient";
import { resolveFovuxHome } from "./paths";

let managedProcess: ChildProcessWithoutNullStreams | null = null;
let startPromise: Promise<void> | null = null;
let outputChannel: vscode.OutputChannel | null = null;

export async function startFovuxServer(): Promise<void> {
  if (!vscode.workspace.isTrusted) {
    throw new Error(
      "Fovux Server cannot start in an untrusted workspace. Trust this workspace first.",
    );
  }

  if (await isFovuxServerReady()) {
    void vscode.window.showInformationMessage(
      "Fovux server is already running.",
    );
    return;
  }

  const readiness = await getFovuxServerReadiness();
  if (readiness === "missing-token") {
    throw new Error(
      "A Fovux HTTP server is listening, but this workspace has no auth.token file. Check fovux.home/FOVUX_HOME or restart the server so it can create the token.",
    );
  }
  if (readiness === "token-mismatch") {
    throw new Error(
      "A Fovux HTTP server is listening, but it rejected this workspace auth token. Stop the old server, rotate the token, or point Fovux Studio at the same FOVUX_HOME.",
    );
  }

  if (startPromise) {
    return startPromise;
  }

  startPromise = startServerProcess().finally(() => {
    startPromise = null;
  });
  return startPromise;
}

export async function stopFovuxServer(): Promise<void> {
  if (!managedProcess) {
    void vscode.window.showInformationMessage(
      "No Fovux server started by this VS Code window.",
    );
    return;
  }

  const proc = managedProcess;
  managedProcess = null;
  killProcessTree(proc);
  getOutputChannel().appendLine("Stopped managed fovux-mcp server.");
}

export function disposeFovuxServerManager(): void {
  if (managedProcess) {
    killProcessTree(managedProcess);
    managedProcess = null;
  }
  outputChannel?.dispose();
  outputChannel = null;
}

async function startServerProcess(): Promise<void> {
  const config = vscode.workspace.getConfiguration("fovux");
  const command =
    (config.get<string>("serverCommand") ?? "fovux-mcp").trim() || "fovux-mcp";
  const port = config.get<number>("httpPort") ?? 7823;
  const fovuxHome = resolveFovuxHome();
  const args = [
    "serve",
    "--http",
    "--tcp",
    "--host",
    "127.0.0.1",
    "--port",
    String(port),
  ];
  const channel = getOutputChannel();
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const cwd = workspaceFolder ?? path.dirname(fovuxHome);

  channel.appendLine(`Starting ${command} ${args.join(" ")}`);
  channel.appendLine(`FOVUX_HOME=${fovuxHome}`);

  const proc = spawn(command, args, {
    cwd,
    env: { ...process.env, FOVUX_HOME: fovuxHome },
    windowsHide: true,
  });
  managedProcess = proc;

  proc.stdout.on("data", (chunk: Buffer) => appendChunk("stdout", chunk));
  proc.stderr.on("data", (chunk: Buffer) => appendChunk("stderr", chunk));
  proc.once("exit", (code, signal) => {
    channel.appendLine(
      `fovux-mcp server exited code=${code ?? "null"} signal=${signal ?? "null"}`,
    );
    if (managedProcess === proc) {
      managedProcess = null;
    }
  });

  let spawnError: Error | null = null;
  proc.once("error", (error) => {
    spawnError = error;
    channel.appendLine(`Failed to start fovux-mcp: ${error.message}`);
    if (managedProcess === proc) {
      managedProcess = null;
    }
  });

  await waitForServerHealthy(() => spawnError);
  void vscode.window.showInformationMessage("Fovux server started.");
}

async function waitForServerHealthy(
  getSpawnError: () => Error | null,
): Promise<void> {
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    const spawnError = getSpawnError();
    if (spawnError) {
      throw new Error(
        `Could not start fovux-mcp. Check that fovux-mcp is installed and on PATH. ${spawnError.message}`,
      );
    }
    if (await isFovuxServerReady()) {
      return;
    }
    await delay(500);
  }
  const finalSpawnError = getSpawnError();
  if (finalSpawnError) {
    throw new Error(
      `Could not start fovux-mcp. Check that fovux-mcp is installed and on PATH. ${finalSpawnError.message}`,
    );
  }
  throw new Error(
    "fovux-mcp HTTP server did not become healthy within 15 seconds.",
  );
}

async function isFovuxServerListening(): Promise<boolean> {
  try {
    const response = await fetch(`${getFovuxBaseUrl()}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

async function isFovuxServerReady(): Promise<boolean> {
  return (await getFovuxServerReadiness()) === "ready";
}

async function getFovuxServerReadiness(): Promise<
  "offline" | "missing-token" | "token-mismatch" | "ready"
> {
  if (!(await isFovuxServerListening())) {
    return "offline";
  }

  const authToken = await getAuthToken();
  if (!authToken) {
    return "missing-token";
  }

  try {
    const response = await fetch(`${getFovuxBaseUrl()}/runs`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });
    return response.ok ? "ready" : "token-mismatch";
  } catch {
    return "offline";
  }
}

function killProcessTree(proc: ChildProcessWithoutNullStreams): void {
  if (process.platform === "win32" && proc.pid !== undefined) {
    execFile("taskkill", ["/PID", String(proc.pid), "/T", "/F"], (error) => {
      if (error) {
        proc.kill();
      }
    });
    return;
  }
  proc.kill();
}

function appendChunk(stream: "stdout" | "stderr", chunk: Buffer): void {
  const text = chunk.toString("utf8").trimEnd();
  if (!text) {
    return;
  }
  getOutputChannel().appendLine(`[${stream}] ${text}`);
}

function getOutputChannel(): vscode.OutputChannel {
  outputChannel ??= vscode.window.createOutputChannel("Fovux Server");
  return outputChannel;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

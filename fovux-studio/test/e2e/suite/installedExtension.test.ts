import assert from "node:assert/strict";
import { realpathSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";
import { join } from "node:path";

import * as vscode from "vscode";

interface FovuxRuntimeState {
  workspaceTrusted: boolean;
  telemetryEnabled: false;
  extensionVersion: string;
  contributedCommands: string[];
}

interface DashboardWebviewDiagnostics {
  opened: boolean;
  ready: boolean;
  contentSecurityPolicy: string | null;
  bundleUri: string | null;
}

interface FovuxStudioApi {
  getRuntimeState(): FovuxRuntimeState;
  getDashboardDiagnostics(): DashboardWebviewDiagnostics;
}

interface DashboardInitialState {
  baseUrl: string;
  initialError: string | null;
  isServerReachable: boolean;
}

interface RecordedRequest {
  method: string | undefined;
  url: string | undefined;
  authorization: string | undefined;
  body: string;
}

export interface E2eTestOutcome {
  name: string;
  status: "passed" | "skipped";
}

const extensionId = "oaslananka.fovuxstudiokit";
const mode = requiredEnvironment("FOVUX_E2E_MODE");
const expectedExtensionPath = requiredEnvironment("FOVUX_E2E_EXTENSION_PATH");
const fovuxHome = requiredEnvironment("FOVUX_HOME");
const offlinePort = 65_534;

export async function runInstalledExtensionAssertions(): Promise<E2eTestOutcome[]> {
  assert.ok(mode === "trusted" || mode === "untrusted", "FOVUX_E2E_MODE is invalid");
  await updateHttpPort(offlinePort);

  const extension = vscode.extensions.getExtension<FovuxStudioApi>(extensionId);
  assert.ok(extension, `${extensionId} is not installed`);
  const api = await extension.activate();
  const outcomes: E2eTestOutcome[] = [];

  await runCase(outcomes, "loads the installed VSIX rather than the source extension", () => {
    assert.equal(realpathSync(extension.extensionPath), realpathSync(expectedExtensionPath));
    assert.equal(extension.isActive, true);
  });

  await runCase(
    outcomes,
    "reports trust, no telemetry, version, and registered commands",
    async () => {
      const state = api.getRuntimeState();
      assert.equal(state.workspaceTrusted, mode === "trusted");
      assert.equal(state.telemetryEnabled, false);
      assert.match(state.extensionVersion, /^\d+\.\d+\.\d+$/);
      assert.ok(state.contributedCommands.length >= 20);

      const registered = new Set(await vscode.commands.getCommands(true));
      for (const command of state.contributedCommands) {
        assert.ok(registered.has(command), `missing registered command ${command}`);
      }
    }
  );

  await runCase(
    outcomes,
    "loads the real dashboard bundle and completes the CSP-protected message handshake",
    async () => {
      const state =
        await vscode.commands.executeCommand<DashboardInitialState>("fovux.openDashboard");

      assert.ok(state, "dashboard command did not return initial state");
      assert.equal(state.baseUrl, `http://127.0.0.1:${offlinePort}`);
      assert.equal(state.isServerReachable, false);
      assert.match(state.initialError ?? "", /HTTP server is offline/);

      await waitFor(() => api.getDashboardDiagnostics().ready, 15_000);
      const diagnostics = api.getDashboardDiagnostics();
      assert.equal(diagnostics.opened, true);
      assert.equal(diagnostics.ready, true);
      assert.match(diagnostics.contentSecurityPolicy ?? "", /default-src 'none'/);
      assert.match(diagnostics.contentSecurityPolicy ?? "", /connect-src http:\/\/127\.0\.0\.1:\*/);
      assert.match(diagnostics.contentSecurityPolicy ?? "", /script-src .*'nonce-[A-Za-z0-9_-]+'/);
      assert.doesNotMatch(diagnostics.contentSecurityPolicy ?? "", /unsafe-eval/);
      assert.match(diagnostics.bundleUri ?? "", /webviews\/dashboard\/main\.js/);

      const webviewTab = vscode.window.tabGroups.all
        .flatMap((group) => group.tabs)
        .find((tab) => tab.label === "Fovux Dashboard");
      assert.ok(webviewTab, "Fovux Dashboard webview tab did not open");
    }
  );

  if (mode === "trusted") {
    await runCase(outcomes, "detects an auth-token mismatch before spawning a server", async () => {
      await writeAuthToken("wrong-e2e-token");
      const fakeServer = await startFakeServer(async (request, response) => {
        if (request.url === "/health") {
          respondJson(response, 200, { status: "ok" });
          return;
        }
        if (request.url === "/runs") {
          respondJson(response, 401, { detail: "token mismatch" });
          return;
        }
        respondJson(response, 404, { detail: "not found" });
      });

      try {
        await updateHttpPort(fakeServer.port);
        await assert.rejects(
          async () => vscode.commands.executeCommand("fovux.startServer"),
          /rejected this workspace auth token/i
        );
      } finally {
        await updateHttpPort(offlinePort);
        await fakeServer.close();
      }
    });
  } else {
    skipCase(outcomes, "detects an auth-token mismatch before spawning a server");
  }

  if (mode === "trusted" && vscode.lm?.invokeTool) {
    await runCase(
      outcomes,
      "invokes a Language Model tool through the installed extension",
      async () => {
        await writeAuthToken("lm-e2e-token");
        let recordedRequest: RecordedRequest | undefined;
        const fakeServer = await startFakeServer(async (request, response) => {
          const body = await readRequestBody(request);
          recordedRequest = {
            method: request.method,
            url: request.url,
            authorization: request.headers.authorization,
            body,
          };
          respondJson(response, 200, { status: "ok", source: "installed-vsix-e2e" });
        });

        try {
          await updateHttpPort(fakeServer.port);
          const result = await vscode.lm.invokeTool("fovux_run_doctor", {
            input: {},
            toolInvocationToken: undefined,
          });
          const output = result.content
            .map((part) =>
              part && typeof part === "object" && "value" in part
                ? String((part as { value: unknown }).value)
                : ""
            )
            .join("\n");

          assert.deepEqual(recordedRequest, {
            method: "POST",
            url: "/tools/fovux_doctor",
            authorization: "Bearer lm-e2e-token",
            body: "{}",
          });
          assert.match(output, /installed-vsix-e2e/);
        } finally {
          await updateHttpPort(offlinePort);
          await fakeServer.close();
        }
      }
    );
  } else {
    skipCase(outcomes, "invokes a Language Model tool through the installed extension");
  }

  if (mode === "untrusted") {
    await runCase(outcomes, "blocks server startup in an untrusted workspace", async () => {
      assert.equal(api.getRuntimeState().workspaceTrusted, false);
      await assert.rejects(
        async () => vscode.commands.executeCommand("fovux.startServer"),
        /cannot start in an untrusted workspace/i
      );
    });
  } else {
    skipCase(outcomes, "blocks server startup in an untrusted workspace");
  }

  return outcomes;
}

async function runCase(
  outcomes: E2eTestOutcome[],
  name: string,
  assertion: () => void | Promise<void>
): Promise<void> {
  try {
    await assertion();
    outcomes.push({ name, status: "passed" });
    process.stdout.write(`[Fovux E2E] PASS: ${name}\n`);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`${name}: ${detail}`, { cause: error });
  }
}

function skipCase(outcomes: E2eTestOutcome[], name: string): void {
  outcomes.push({ name, status: "skipped" });
  process.stdout.write(`[Fovux E2E] SKIP: ${name}\n`);
}

async function startFakeServer(
  handler: (request: IncomingMessage, response: ServerResponse) => Promise<void>
): Promise<{ port: number; close: () => Promise<void> }> {
  const server = createServer((request, response) => {
    void handler(request, response).catch((error: unknown) => {
      respondJson(response, 500, {
        detail: error instanceof Error ? error.message : String(error),
      });
    });
  });
  await new Promise<void>((resolveListen, rejectListen) => {
    server.once("error", rejectListen);
    server.listen(0, "127.0.0.1", () => resolveListen());
  });
  const address = server.address();
  assert.ok(address && typeof address !== "string", "fake server did not expose a TCP address");
  return {
    port: (address as AddressInfo).port,
    close: () => closeServer(server),
  };
}

async function closeServer(server: Server): Promise<void> {
  await new Promise<void>((resolveClose, rejectClose) => {
    server.close((error) => (error ? rejectClose(error) : resolveClose()));
  });
}

async function readRequestBody(request: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf8");
}

function respondJson(response: ServerResponse, status: number, payload: unknown): void {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(payload));
}

async function writeAuthToken(token: string): Promise<void> {
  await writeFile(join(fovuxHome, "auth.token"), `${token}\n`, "utf8");
}

async function updateHttpPort(port: number): Promise<void> {
  await vscode.workspace
    .getConfiguration("fovux")
    .update("httpPort", port, vscode.ConfigurationTarget.Global);
}

async function waitFor(predicate: () => boolean, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) {
      return;
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 100));
  }
  throw new Error(`condition was not met within ${timeoutMs}ms`);
}

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}

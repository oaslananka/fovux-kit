import assert from "node:assert/strict";
import { realpathSync } from "node:fs";

import * as vscode from "vscode";

interface FovuxRuntimeState {
  workspaceTrusted: boolean;
  telemetryEnabled: false;
  extensionVersion: string;
  contributedCommands: string[];
}

interface FovuxStudioApi {
  getRuntimeState(): FovuxRuntimeState;
}

interface DashboardInitialState {
  baseUrl: string;
  initialError: string | null;
  isServerReachable: boolean;
}

const extensionId = "oaslananka.fovuxstudiokit";
const mode = requiredEnvironment("FOVUX_E2E_MODE");
const expectedExtensionPath = requiredEnvironment("FOVUX_E2E_EXTENSION_PATH");
let extension: vscode.Extension<FovuxStudioApi>;
let api: FovuxStudioApi;

suite(`Fovux Studio installed VSIX (${mode})`, () => {
  suiteSetup(async () => {
    assert.ok(mode === "trusted" || mode === "untrusted", "FOVUX_E2E_MODE is invalid");
    await vscode.workspace
      .getConfiguration("fovux")
      .update("httpPort", 65_534, vscode.ConfigurationTarget.Global);

    const installed = vscode.extensions.getExtension<FovuxStudioApi>(extensionId);
    assert.ok(installed, `${extensionId} is not installed`);
    extension = installed;
    api = await extension.activate();
  });

  test("loads the installed VSIX rather than the source extension", () => {
    assert.equal(realpathSync(extension.extensionPath), realpathSync(expectedExtensionPath));
    assert.equal(extension.isActive, true);
  });

  test("reports trust, no telemetry, version, and registered commands", async () => {
    const state = api.getRuntimeState();
    assert.equal(state.workspaceTrusted, mode === "trusted");
    assert.equal(state.telemetryEnabled, false);
    assert.match(state.extensionVersion, /^\d+\.\d+\.\d+$/);
    assert.ok(state.contributedCommands.length >= 20);

    const registered = new Set(await vscode.commands.getCommands(true));
    for (const command of state.contributedCommands) {
      assert.ok(registered.has(command), `missing registered command ${command}`);
    }
  });

  test("registers the generic Language Model tool when the API is available", () => {
    if (!vscode.lm?.tools) {
      return;
    }
    assert.ok(vscode.lm.tools.some((tool) => tool.name === "fovux_call_tool"));
  });

  test("opens the real dashboard webview with deterministic backend-offline state", async () => {
    const state =
      await vscode.commands.executeCommand<DashboardInitialState>("fovux.openDashboard");

    assert.ok(state, "dashboard command did not return initial state");
    assert.equal(state.baseUrl, "http://127.0.0.1:65534");
    assert.equal(state.isServerReachable, false);
    assert.match(state.initialError ?? "", /HTTP server is offline/);

    const webviewTab = vscode.window.tabGroups.all
      .flatMap((group) => group.tabs)
      .find((tab) => tab.label === "Fovux Dashboard");
    assert.ok(webviewTab, "Fovux Dashboard webview tab did not open");
  });

  test("blocks server startup in an untrusted workspace", async function () {
    if (mode !== "untrusted") {
      this.skip();
    }
    assert.equal(api.getRuntimeState().workspaceTrusted, false);
    await assert.rejects(
      async () => vscode.commands.executeCommand("fovux.startServer"),
      /cannot start in an untrusted workspace/i
    );
  });
});

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}

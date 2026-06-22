import * as path from "node:path";
import * as vscode from "vscode";

import { ExtensionFovuxClient, RunSummary } from "../fovux/extensionClient";
import {
  getSessionActiveFovuxProfile,
  resolveFovuxHome,
  resolveFovuxProfiles,
} from "../fovux/paths";
import { startFovuxServer } from "../fovux/serverManager";
import { createWebviewHtml } from "../webviews/html";
import { DashboardInitialState, WebviewToExtensionMessage } from "../webviews/shared/types";

export async function openDashboard(context: vscode.ExtensionContext): Promise<void> {
  const panel = vscode.window.createWebviewPanel(
    "fovux.dashboard",
    "Fovux Dashboard",
    vscode.ViewColumn.One,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [context.extensionUri],
    }
  );

  panel.webview.onDidReceiveMessage((message: WebviewToExtensionMessage) => {
    if (message.type === "openPath") {
      void vscode.commands.executeCommand("revealFileInOS", vscode.Uri.file(message.path));
      return;
    }
    if (message.type === "triggerCommand") {
      const allowedCommands = new Set([
        "fovux.openDatasetInspector",
        "fovux.openExportWizard",
        "fovux.startTraining",
        "fovux.openDashboard",
      ]);
      if (!allowedCommands.has(message.command)) {
        void vscode.window.showErrorMessage(`Blocked webview command: ${message.command}`);
        return;
      }
      void vscode.commands.executeCommand(message.command, ...(message.args ?? []));
      return;
    }
    if (message.type === "startServer") {
      void startFovuxServer()
        .then(() => renderDashboard(panel, context))
        .catch((error: unknown) => {
          void vscode.window.showErrorMessage(
            error instanceof Error ? error.message : String(error)
          );
        });
      return;
    }
    if (message.type === "selectFovuxProfile") {
      const fovuxConfig = vscode.workspace.getConfiguration("fovux");
      void fovuxConfig
        .update("activeProfile", message.profile.name, vscode.ConfigurationTarget.Global)
        .then(() => {
          void vscode.commands.executeCommand("fovux.refreshViews");
          return renderDashboard(panel, context);
        });
      return;
    }
    if (message.type === "initializeDemoWorkspace") {
      void (async () => {
        try {
          const home = resolveFovuxHome();
          const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
          const rootDir = workspaceFolder ?? home;
          const demoPath = path.join(rootDir, "demo_workspace");

          const fovuxConfig = vscode.workspace.getConfiguration("fovux");
          await fovuxConfig.update("home", demoPath, vscode.ConfigurationTarget.Global);

          const extensionClient = await ExtensionFovuxClient.create();
          const serverRunning = await extensionClient.health();
          if (!serverRunning) {
            await startFovuxServer();
          }

          let retries = 10;
          let ok = false;
          while (retries > 0 && !ok) {
            ok = await extensionClient.health();
            if (!ok) {
              await new Promise((resolve) => setTimeout(resolve, 500));
              retries--;
            }
          }

          if (!ok) {
            throw new Error("Local Fovux server did not become responsive.");
          }

          await extensionClient.invokeTool("demo_init", { target_path: demoPath });

          void vscode.window.showInformationMessage(`Demo workspace initialized at: ${demoPath}`);
          void vscode.commands.executeCommand("fovux.refreshViews");
          await renderDashboard(panel, context);
        } catch (error) {
          void vscode.window.showErrorMessage(
            error instanceof Error ? error.message : String(error)
          );
        }
      })();
      return;
    }
  });

  await renderDashboard(panel, context);
}

async function renderDashboard(
  panel: vscode.WebviewPanel,
  context: vscode.ExtensionContext
): Promise<void> {
  const config = vscode.workspace.getConfiguration("fovux");
  const client = await ExtensionFovuxClient.create();
  const isServerReachable = await client.health();
  let initialRuns: RunSummary[] = [];
  let initialError: string | null = null;

  if (isServerReachable) {
    try {
      initialRuns = await client.listRuns();
    } catch (error) {
      initialError = error instanceof Error ? error.message : String(error);
    }
  } else {
    initialError =
      "fovux-mcp HTTP server is offline. Start `fovux-mcp serve --http` to stream runs.";
  }

  const fovuxHome = resolveFovuxHome();
  const activeProfile =
    getSessionActiveFovuxProfile() ?? config.get<string>("activeProfile") ?? "default";
  const availableProfiles = resolveFovuxProfiles();

  const datasetUris =
    typeof vscode.workspace.findFiles === "function"
      ? await vscode.workspace.findFiles("**/data.yaml", "**/node_modules/**", 10)
      : [];
  const discoveredDatasets = datasetUris.map((uri) => uri.fsPath);

  const initialState: DashboardInitialState = {
    baseUrl: client.getBaseUrl(),
    authToken: client.getAuthToken(),
    pollIntervalMs: config.get<number>("pollIntervalMs") ?? 2000,
    initialRuns,
    initialError,
    isServerReachable,
    fovuxHome,
    activeProfile,
    availableProfiles,
    discoveredDatasets,
  };

  panel.webview.html = createWebviewHtml(
    panel.webview,
    context.extensionUri,
    "webviews/dashboard/main.js",
    initialState
  );
}

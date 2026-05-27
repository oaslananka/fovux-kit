import * as vscode from "vscode";

import { ExtensionFovuxClient, RunSummary } from "../fovux/extensionClient";
import { startFovuxServer } from "../fovux/serverManager";
import { createWebviewHtml } from "../webviews/html";
import { CompareRunsInitialState, WebviewToExtensionMessage } from "../webviews/shared/types";

export async function openCompareRuns(context: vscode.ExtensionContext): Promise<void> {
  const panel = vscode.window.createWebviewPanel(
    "fovux.compareRuns",
    "Fovux Run Comparison",
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
    if (message.type === "startServer") {
      void startFovuxServer()
        .then(() => renderCompareRuns(panel, context))
        .catch((error: unknown) => {
          void vscode.window.showErrorMessage(
            error instanceof Error ? error.message : String(error)
          );
        });
    }
  });

  await renderCompareRuns(panel, context);
}

async function renderCompareRuns(
  panel: vscode.WebviewPanel,
  context: vscode.ExtensionContext
): Promise<void> {
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
      "fovux-mcp HTTP server is offline. Start `fovux-mcp serve --http` before comparing runs.";
  }

  const initialState: CompareRunsInitialState = {
    baseUrl: client.getBaseUrl(),
    authToken: client.getAuthToken(),
    initialRuns,
    initialError,
    isServerReachable,
  };

  panel.webview.html = createWebviewHtml(
    panel.webview,
    context.extensionUri,
    "webviews/compareRuns/main.js",
    initialState
  );
}

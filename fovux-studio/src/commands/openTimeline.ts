import * as vscode from "vscode";

import { ExtensionFovuxClient, type RunSummary } from "../fovux/extensionClient";
import { startFovuxServer } from "../fovux/serverManager";
import { createWebviewHtml } from "../webviews/html";
import type { TimelineInitialState, WebviewToExtensionMessage } from "../webviews/shared/types";

export async function openTimeline(context: vscode.ExtensionContext): Promise<void> {
  const panel = vscode.window.createWebviewPanel(
    "fovux.timeline",
    "Fovux Run Timeline",
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
        .then(() => renderTimeline(panel, context))
        .catch((error: unknown) => {
          void vscode.window.showErrorMessage(
            error instanceof Error ? error.message : String(error)
          );
        });
    }
  });

  await renderTimeline(panel, context);
}

async function renderTimeline(
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
    initialError = "fovux-mcp HTTP server is offline. Start it to load the run timeline.";
  }

  const initialState: TimelineInitialState = {
    baseUrl: client.getBaseUrl(),
    authToken: client.getAuthToken(),
    initialRuns,
    initialError,
    isServerReachable,
  };

  panel.webview.html = createWebviewHtml(
    panel.webview,
    context.extensionUri,
    "webviews/timeline/main.js",
    initialState
  );
}

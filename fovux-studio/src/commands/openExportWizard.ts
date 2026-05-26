import * as vscode from "vscode";

import { ExtensionFovuxClient } from "../fovux/extensionClient";
import { resolveFovuxHome } from "../fovux/paths";
import { startFovuxServer } from "../fovux/serverManager";
import { createWebviewHtml } from "../webviews/html";
import {
  ExportWizardInitialState,
  ExportWizardModelArtifact,
  WebviewToExtensionMessage,
} from "../webviews/shared/types";

export async function openExportWizard(context: vscode.ExtensionContext): Promise<void> {
  const panel = vscode.window.createWebviewPanel(
    "fovux.exportWizard",
    "Fovux Export Wizard",
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
        .then(() => renderExportWizard(panel, context))
        .catch((error: unknown) => {
          void vscode.window.showErrorMessage(
            error instanceof Error ? error.message : String(error)
          );
        });
    }
  });

  await renderExportWizard(panel, context);
}

async function renderExportWizard(
  panel: vscode.WebviewPanel,
  context: vscode.ExtensionContext
): Promise<void> {
  const client = await ExtensionFovuxClient.create();
  const isServerReachable = await client.health();
  let initialModels: ExportWizardModelArtifact[] = [];
  let initialError: string | null = null;

  if (isServerReachable) {
    try {
      const response = await client.invokeTool<{ models: ExportWizardModelArtifact[] }>(
        "model_list",
        {}
      );
      initialModels = response.models;
    } catch (error) {
      initialError = error instanceof Error ? error.message : String(error);
    }
  } else {
    initialError =
      "fovux-mcp HTTP server is offline. Start `fovux-mcp serve --http` before exporting.";
  }

  const initialState: ExportWizardInitialState = {
    baseUrl: client.getBaseUrl(),
    authToken: client.getAuthToken(),
    initialModels,
    fovuxHome: resolveFovuxHome(),
    initialError,
    isServerReachable,
  };

  panel.webview.html = createWebviewHtml(
    panel.webview,
    context.extensionUri,
    "webviews/exportWizard/main.js",
    initialState
  );
}

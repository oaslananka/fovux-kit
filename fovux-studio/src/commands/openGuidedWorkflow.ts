import * as vscode from "vscode";
import { GUIDED_WORKFLOW_STAGES } from "../fovux/guidedWorkflow";
import { createWebviewHtml } from "../webviews/html";

export async function openGuidedWorkflow(context: vscode.ExtensionContext): Promise<void> {
  const panel = vscode.window.createWebviewPanel(
    "fovux.guidedWorkflow",
    "Fovux Guided Workflow",
    vscode.ViewColumn.One,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [context.extensionUri],
    }
  );
  panel.webview.html = createWebviewHtml(
    panel.webview,
    context.extensionUri,
    "webviews/guidedWorkflow/main.js",
    { stages: GUIDED_WORKFLOW_STAGES }
  );
}

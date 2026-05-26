import * as path from "node:path";
import * as vscode from "vscode";

import { ExtensionFovuxClient } from "../fovux/extensionClient";
import { createWebviewHtml } from "../webviews/html";
import { buildDatasetSamples } from "../webviews/datasetInspector/sampleData";
import {
  DatasetInspectorInitialState,
  DatasetSample,
  WebviewToExtensionMessage,
} from "../webviews/shared/types";

export async function openDatasetInspector(
  context: vscode.ExtensionContext,
  providedDatasetPath?: string,
): Promise<void> {
  const datasetPath = providedDatasetPath ?? (await pickDatasetPath());
  if (!datasetPath) {
    return;
  }
  const panel = vscode.window.createWebviewPanel(
    "fovux.datasetInspector",
    "Fovux Dataset Inspector",
    vscode.ViewColumn.One,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [context.extensionUri, vscode.Uri.file(datasetPath)],
    },
  );

  panel.webview.onDidReceiveMessage((message: WebviewToExtensionMessage) => {
    if (message.type === "openPath") {
      void vscode.commands.executeCommand(
        "revealFileInOS",
        vscode.Uri.file(message.path),
      );
    }
  });

  const client = await ExtensionFovuxClient.create();
  let initialResult: Record<string, unknown> | null = null;
  let initialError: string | null = null;
  let samplePreviews: DatasetSample[] = [];

  try {
    initialResult = await client.invokeTool<Record<string, unknown>>(
      "dataset_inspect",
      {
        dataset_path: datasetPath,
      },
    );
    samplePreviews = await extractSamplePreviews(
      panel.webview,
      datasetPath,
      initialResult,
    );
  } catch (error) {
    initialError = error instanceof Error ? error.message : String(error);
  }

  const initialState: DatasetInspectorInitialState = {
    baseUrl: client.getBaseUrl(),
    authToken: client.getAuthToken(),
    datasetPath,
    initialResult,
    samplePreviews,
    initialError,
  };

  panel.webview.html = createWebviewHtml(
    panel.webview,
    context.extensionUri,
    "webviews/datasetInspector/main.js",
    initialState,
  );
}

async function pickDatasetPath(): Promise<string | null> {
  const selection = await vscode.window.showOpenDialog({
    canSelectFiles: false,
    canSelectFolders: true,
    canSelectMany: false,
    openLabel: "Inspect Dataset",
  });
  return selection?.[0]?.fsPath ?? null;
}

async function extractSamplePreviews(
  webview: vscode.Webview,
  datasetPath: string,
  result: Record<string, unknown>,
): Promise<DatasetSample[]> {
  const rawPaths = result["sample_paths"];
  if (!Array.isArray(rawPaths)) {
    return [];
  }

  const samplePaths = rawPaths.filter(
    (value): value is string => typeof value === "string",
  );
  return buildDatasetSamples({
    datasetPath,
    samplePaths,
    classNames: extractClassNames(result),
    toWebviewUri: (samplePath) =>
      webview
        .asWebviewUri(vscode.Uri.file(path.resolve(samplePath)))
        .toString(),
  });
}

function extractClassNames(result: Record<string, unknown>): string[] {
  const rawClasses = result["classes"];
  if (!Array.isArray(rawClasses)) {
    return [];
  }
  return rawClasses
    .map((entry) =>
      typeof entry === "object" && entry !== null ? entry["name"] : null,
    )
    .filter((value): value is string => typeof value === "string");
}

import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as vscode from "vscode";

import { createWebviewHtml } from "../webviews/html";
import { resolveLabelPath } from "../webviews/datasetInspector/sampleData";
import type {
  AnnotationEditorInitialState,
  DatasetSampleBox,
  WebviewToExtensionMessage,
} from "../webviews/shared/types";

export async function openAnnotationEditor(context: vscode.ExtensionContext): Promise<void> {
  const selection = await vscode.window.showOpenDialog({
    canSelectFiles: true,
    canSelectFolders: false,
    canSelectMany: false,
    openLabel: "Annotate Image",
    filters: { Images: ["jpg", "jpeg", "png", "bmp", "webp"] },
  });

  if (!selection?.length) {
    return;
  }

  const imagePath = selection[0].fsPath;
  const datasetPath = inferDatasetRoot(imagePath) ?? path.dirname(imagePath);
  const panel = vscode.window.createWebviewPanel(
    "fovux.annotationEditor",
    "Fovux Annotation Editor",
    vscode.ViewColumn.One,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [context.extensionUri, vscode.Uri.file(path.dirname(imagePath))],
    }
  );

  panel.webview.onDidReceiveMessage((message: WebviewToExtensionMessage) => {
    if (message.type === "saveAnnotation") {
      void saveAnnotation(datasetPath, message.imagePath, message.boxes)
        .then((labelPath) => vscode.window.showInformationMessage(`Saved ${labelPath}`))
        .then(undefined, (error: unknown) => {
          void vscode.window.showErrorMessage(
            error instanceof Error ? error.message : String(error)
          );
        });
    }
  });

  const initialState: AnnotationEditorInitialState = {
    imagePath,
    imageUri: panel.webview.asWebviewUri(vscode.Uri.file(imagePath)).toString(),
    classNames: ["class_0"],
    initialBoxes: await loadAnnotationBoxes(datasetPath, imagePath),
    initialError: null,
  };

  panel.webview.html = createWebviewHtml(
    panel.webview,
    context.extensionUri,
    "webviews/annotationEditor/main.js",
    initialState
  );
}

async function saveAnnotation(
  datasetPath: string,
  imagePath: string,
  boxes: DatasetSampleBox[]
): Promise<string> {
  const labelPath = resolveLabelPath(datasetPath, imagePath);
  if (labelPath === null) {
    throw new Error("Image must live under a YOLO images/ directory to save labels.");
  }
  const lines = boxes.map((box) => {
    const centerX = box.x + box.width / 2;
    const centerY = box.y + box.height / 2;
    return `${box.classId} ${centerX.toFixed(6)} ${centerY.toFixed(6)} ${box.width.toFixed(
      6
    )} ${box.height.toFixed(6)}`;
  });
  await fs.mkdir(path.dirname(labelPath), { recursive: true });
  await fs.writeFile(labelPath, `${lines.join("\n")}${lines.length ? "\n" : ""}`, "utf-8");
  return labelPath;
}

async function loadAnnotationBoxes(
  datasetPath: string,
  imagePath: string
): Promise<DatasetSampleBox[]> {
  const labelPath = resolveLabelPath(datasetPath, imagePath);
  if (labelPath === null) {
    return [];
  }
  try {
    const raw = await fs.readFile(labelPath, "utf-8");
    return raw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .flatMap((line) => {
        const parts = line.split(/\s+/).map(Number);
        if (parts.length < 5 || parts.some(Number.isNaN)) {
          return [];
        }
        const [classId, centerX, centerY, width, height] = parts;
        return [
          {
            classId,
            className: `class_${classId}`,
            x: clamp(centerX - width / 2),
            y: clamp(centerY - height / 2),
            width: clamp(width),
            height: clamp(height),
          },
        ];
      });
  } catch {
    return [];
  }
}

function inferDatasetRoot(imagePath: string): string | null {
  const normalized = imagePath.replace(/\\/g, "/");
  const marker = "/images/";
  const index = normalized.lastIndexOf(marker);
  if (index === -1) {
    return null;
  }
  return imagePath.slice(0, index);
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value));
}

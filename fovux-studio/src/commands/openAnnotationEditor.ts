import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as vscode from "vscode";

import { createWebviewHtml } from "../webviews/html";
import { resolveLabelPath } from "../webviews/datasetInspector/sampleData";
import { ExtensionFovuxClient } from "../fovux/extensionClient";
import type {
  AnnotationEditorInitialState,
  DatasetSampleBox,
  WebviewToExtensionMessage,
} from "../webviews/shared/types";

interface QueueDetection {
  class_id: number;
  class_name: string;
  confidence: number;
  bbox_xyxy: number[];
}

interface ActiveLearningQueueItem {
  id: string;
  image_path: string;
  dataset_path: string;
  score: number;
  reason: string;
  status: string;
  predictions: QueueDetection[];
  corrected_labels?: QueueDetection[];
  created_at?: string;
}

interface DatasetClassEntry {
  name: string;
  id?: number;
}

interface DatasetInspectResult {
  classes?: DatasetClassEntry[];
}

export async function openAnnotationEditor(
  context: vscode.ExtensionContext,
  options?: { isQueueMode?: boolean; datasetPath?: string }
): Promise<void> {
  const client = await ExtensionFovuxClient.create();

  if (options?.isQueueMode) {
    let queue: ActiveLearningQueueItem[] = [];
    try {
      const res = await client.invokeTool<{
        queue_entries: ActiveLearningQueueItem[];
      }>("active_learning_queue_list", {
        dataset_path: options.datasetPath,
        status: "pending",
        limit: 100,
      });
      queue = res.queue_entries || [];
    } catch (error) {
      void vscode.window.showErrorMessage(
        `Failed to load review queue: ${error instanceof Error ? error.message : String(error)}`
      );
      return;
    }

    if (queue.length === 0) {
      void vscode.window.showInformationMessage("No pending items in the active learning queue.");
      return;
    }

    const firstItem = queue[0];
    let classNames = ["class_0"];
    try {
      const inspectResult = await client.invokeTool<DatasetInspectResult>("dataset_inspect", {
        dataset_path: firstItem.dataset_path,
      });
      if (inspectResult && Array.isArray(inspectResult.classes)) {
        classNames = inspectResult.classes
          .map((c) => (c && typeof c === "object" ? c.name : null))
          .filter((n): n is string => typeof n === "string");
      }
    } catch {
      // fallback
    }

    const initialBoxes: DatasetSampleBox[] = (firstItem.predictions || []).map((p) => ({
      classId: p.class_id,
      className: p.class_name || `class_${p.class_id}`,
      x: p.bbox_xyxy[0],
      y: p.bbox_xyxy[1],
      width: p.bbox_xyxy[2],
      height: p.bbox_xyxy[3],
    }));

    const localResourceRoots = [
      context.extensionUri,
      vscode.Uri.file(path.dirname(firstItem.image_path)),
      vscode.Uri.file(firstItem.dataset_path),
    ];
    if (vscode.workspace.workspaceFolders) {
      for (const folder of vscode.workspace.workspaceFolders) {
        localResourceRoots.push(folder.uri);
      }
    }

    const panel = vscode.window.createWebviewPanel(
      "fovux.annotationEditor",
      "Fovux Annotation Editor Queue",
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots,
      }
    );

    let currentIndex = 0;

    const loadQueueItem = async (index: number) => {
      if (index >= queue.length) {
        try {
          const res = await client.invokeTool<{
            queue_entries: ActiveLearningQueueItem[];
          }>("active_learning_queue_list", {
            dataset_path: options.datasetPath,
            status: "pending",
            limit: 100,
          });
          queue = res.queue_entries || [];
          currentIndex = 0;
        } catch {
          queue = [];
        }
        if (queue.length === 0) {
          void vscode.window.showInformationMessage("All pending queue items have been reviewed.");
          panel.dispose();
          return;
        }
      }

      const item = queue[currentIndex];
      let itemClassNames = ["class_0"];
      try {
        const inspectResult = await client.invokeTool<DatasetInspectResult>("dataset_inspect", {
          dataset_path: item.dataset_path,
        });
        if (inspectResult && Array.isArray(inspectResult.classes)) {
          itemClassNames = inspectResult.classes
            .map((c) => (c && typeof c === "object" ? c.name : null))
            .filter((n): n is string => typeof n === "string");
        }
      } catch {
        // fallback
      }

      const itemBoxes: DatasetSampleBox[] = (item.predictions || []).map((p) => ({
        classId: p.class_id,
        className: p.class_name || `class_${p.class_id}`,
        x: p.bbox_xyxy[0],
        y: p.bbox_xyxy[1],
        width: p.bbox_xyxy[2],
        height: p.bbox_xyxy[3],
      }));

      const state: AnnotationEditorInitialState = {
        imagePath: item.image_path,
        imageUri: panel.webview.asWebviewUri(vscode.Uri.file(item.image_path)).toString(),
        classNames: itemClassNames,
        initialBoxes: itemBoxes,
        initialError: null,
        isQueueMode: true,
        queueReason: item.reason,
        queueScore: item.score,
        queueEntryId: item.id,
        datasetPath: item.dataset_path,
      };

      void panel.webview.postMessage({ type: "setEditorState", state });
    };

    panel.webview.onDidReceiveMessage((message: WebviewToExtensionMessage) => {
      if (message.type === "submitQueueEntry") {
        const correctedLabels = message.boxes.map((b) => ({
          class_id: b.classId,
          class_name: b.className,
          confidence: 1.0,
          bbox_xyxy: [b.x, b.y, b.width, b.height],
        }));
        void client
          .invokeTool("active_learning_queue_submit", {
            entry_id: message.entryId,
            corrected_labels: correctedLabels,
            dataset_split: message.datasetSplit || "train",
          })
          .then(() => {
            void vscode.window.showInformationMessage("Label corrections submitted successfully.");
            currentIndex++;
            return loadQueueItem(currentIndex);
          })
          .then(undefined, (error: unknown) => {
            void vscode.window.showErrorMessage(
              `Failed to submit: ${error instanceof Error ? error.message : String(error)}`
            );
          });
      } else if (message.type === "skipQueueEntry") {
        currentIndex++;
        void loadQueueItem(currentIndex);
      }
    });

    const initialState: AnnotationEditorInitialState = {
      imagePath: firstItem.image_path,
      imageUri: panel.webview.asWebviewUri(vscode.Uri.file(firstItem.image_path)).toString(),
      classNames,
      initialBoxes,
      initialError: null,
      isQueueMode: true,
      queueReason: firstItem.reason,
      queueScore: firstItem.score,
      queueEntryId: firstItem.id,
      datasetPath: firstItem.dataset_path,
    };

    panel.webview.html = createWebviewHtml(
      panel.webview,
      context.extensionUri,
      "webviews/annotationEditor/main.js",
      initialState
    );
    return;
  }

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

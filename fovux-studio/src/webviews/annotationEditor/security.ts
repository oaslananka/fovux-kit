import type { AnnotationEditorInitialState, DatasetSampleBox } from "../shared/types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Allow only resource URIs and inert raster images in the annotation canvas. */
export function sanitizeImageUri(uri: unknown): string {
  if (typeof uri !== "string") {
    return "";
  }

  const value = uri.trim();
  if (/^vscode-webview-resource:[^\s"'<>]+$/i.test(value)) {
    return value;
  }

  if (/^data:image\/(?:png|jpeg|gif|webp|bmp|avif);base64,[a-zA-Z0-9+/]+={0,2}$/.test(value)) {
    return value;
  }

  return "";
}

function isBox(value: unknown): value is DatasetSampleBox {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.classId === "number" &&
    Number.isInteger(value.classId) &&
    typeof value.className === "string" &&
    typeof value.x === "number" &&
    Number.isFinite(value.x) &&
    typeof value.y === "number" &&
    Number.isFinite(value.y) &&
    typeof value.width === "number" &&
    Number.isFinite(value.width) &&
    typeof value.height === "number" &&
    Number.isFinite(value.height)
  );
}

/** Runtime validation of opaque initial state and extension-to-webview messages. */
export function sanitizeAnnotationEditorState(
  value: unknown,
  fallback: AnnotationEditorInitialState | null = null
): AnnotationEditorInitialState | null {
  if (
    !isRecord(value) ||
    typeof value.imagePath !== "string" ||
    !Array.isArray(value.classNames) ||
    !value.classNames.every((name: unknown) => typeof name === "string") ||
    !Array.isArray(value.initialBoxes) ||
    !value.initialBoxes.every(isBox) ||
    (value.initialError !== null && typeof value.initialError !== "string") ||
    (value.isQueueMode !== undefined && typeof value.isQueueMode !== "boolean") ||
    (value.queueReason !== undefined && typeof value.queueReason !== "string") ||
    (value.queueScore !== undefined &&
      (typeof value.queueScore !== "number" || !Number.isFinite(value.queueScore))) ||
    (value.queueEntryId !== undefined && typeof value.queueEntryId !== "string") ||
    (value.datasetPath !== undefined && typeof value.datasetPath !== "string")
  ) {
    return fallback;
  }

  const state: AnnotationEditorInitialState = {
    imagePath: value.imagePath as string,
    imageUri: sanitizeImageUri(value.imageUri),
    classNames: value.classNames as string[],
    initialBoxes: value.initialBoxes as DatasetSampleBox[],
    initialError: value.initialError as string | null,
  };

  if (value.isQueueMode !== undefined) {
    state.isQueueMode = value.isQueueMode as boolean;
  }
  if (value.queueReason !== undefined) {
    state.queueReason = value.queueReason as string;
  }
  if (value.queueScore !== undefined) {
    state.queueScore = value.queueScore as number;
  }
  if (value.queueEntryId !== undefined) {
    state.queueEntryId = value.queueEntryId as string;
  }
  if (value.datasetPath !== undefined) {
    state.datasetPath = value.datasetPath as string;
  }

  return state;
}

/** Reject cross-origin and malformed updates before applying editor state. */
export function readTrustedEditorMessage(
  event: Pick<MessageEvent, "origin" | "data">,
  trustedOrigin: string
): AnnotationEditorInitialState | null {
  if (!trustedOrigin || event.origin !== trustedOrigin || !isRecord(event.data)) {
    return null;
  }

  const message = event.data;
  if (message.type !== "setEditorState") {
    return null;
  }

  return sanitizeAnnotationEditorState(message.state);
}

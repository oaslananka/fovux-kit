import type { AnnotationEditorInitialState } from "../shared/types";

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

function isBox(value: unknown): boolean {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.classId === "number" &&
    Number.isInteger(value.classId) &&
    typeof value.className === "string" &&
    ["x", "y", "width", "height"].every(
      (key) => typeof value[key] === "number" && Number.isFinite(value[key])
    )
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
    (value.initialError !== null && typeof value.initialError !== "string")
  ) {
    return fallback;
  }

  return {
    ...(value as unknown as AnnotationEditorInitialState),
    imageUri: sanitizeImageUri(value.imageUri),
  };
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

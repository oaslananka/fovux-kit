import type { AnnotationEditorInitialState } from "../shared/types";

const VS_CODE_RESOURCE_PROTOCOLS = new Set(["vscode-resource:", "vscode-webview-resource:"]);
const VS_CODE_CDN_HOST = "vscode-resource.vscode-cdn.net";
const RASTER_DATA_URI = /^data:image\/(?:png|jpeg|gif|webp);base64,[A-Za-z0-9+/=]+$/;

export function sanitizeAnnotationImageUri(uri: unknown): string {
  if (typeof uri !== "string") {
    return "";
  }

  const value = uri.trim();
  if (!value) {
    return "";
  }

  if (RASTER_DATA_URI.test(value)) {
    return value;
  }

  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return "";
  }

  if (VS_CODE_RESOURCE_PROTOCOLS.has(parsed.protocol)) {
    return value;
  }

  const isVsCodeCdnHost =
    parsed.hostname === VS_CODE_CDN_HOST || parsed.hostname.endsWith(`.${VS_CODE_CDN_HOST}`);
  if (parsed.protocol === "https:" && isVsCodeCdnHost) {
    return value;
  }

  return "";
}

export function sanitizeAnnotationEditorState(
  state: AnnotationEditorInitialState
): AnnotationEditorInitialState {
  return {
    ...state,
    imageUri: sanitizeAnnotationImageUri(state.imageUri),
  };
}

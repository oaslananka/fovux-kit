import { describe, expect, it } from "vitest";

import {
  sanitizeAnnotationEditorState,
  sanitizeAnnotationImageUri,
} from "../../src/webviews/annotationEditor/imageUri";

const BASE_STATE = {
  imagePath: "/data/cat.png",
  imageUri: "",
  classNames: ["cat"],
  initialBoxes: [],
  initialError: null,
};

describe("annotation image URI trust boundary", () => {
  it("accepts VS Code webview resource URIs", () => {
    expect(sanitizeAnnotationImageUri("vscode-resource:/workspace/cat.png")).toBe(
      "vscode-resource:/workspace/cat.png"
    );
    expect(sanitizeAnnotationImageUri("vscode-webview-resource:/workspace/cat.png")).toBe(
      "vscode-webview-resource:/workspace/cat.png"
    );
    expect(
      sanitizeAnnotationImageUri("https://file+.vscode-resource.vscode-cdn.net/workspace/cat.png")
    ).toBe("https://file+.vscode-resource.vscode-cdn.net/workspace/cat.png");
  });

  it("accepts only narrow raster data URIs", () => {
    expect(sanitizeAnnotationImageUri("data:image/png;base64,AAAA")).toBe(
      "data:image/png;base64,AAAA"
    );
    expect(sanitizeAnnotationImageUri("data:image/webp;base64,AAAA")).toBe(
      "data:image/webp;base64,AAAA"
    );
    expect(sanitizeAnnotationImageUri("data:image/svg+xml;base64,AAAA")).toBe("");
  });

  it("rejects external, malformed, empty, and non-string values", () => {
    expect(sanitizeAnnotationImageUri("https://example.com/cat.png")).toBe("");
    expect(sanitizeAnnotationImageUri("not a URI")).toBe("");
    expect(sanitizeAnnotationImageUri("   ")).toBe("");
    expect(sanitizeAnnotationImageUri(null)).toBe("");
  });

  it("sanitizes initial editor state before rendering", () => {
    expect(
      sanitizeAnnotationEditorState({
        ...BASE_STATE,
        imageUri: "https://example.com/cat.png",
      }).imageUri
    ).toBe("");
    expect(
      sanitizeAnnotationEditorState({
        ...BASE_STATE,
        imageUri: "vscode-resource:/workspace/cat.png",
      }).imageUri
    ).toBe("vscode-resource:/workspace/cat.png");
  });
});

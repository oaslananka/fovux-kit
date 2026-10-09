import { describe, expect, it } from "vitest";
import {
  readTrustedEditorMessage,
  sanitizeAnnotationEditorState,
  sanitizeImageUri,
} from "../../src/webviews/annotationEditor/security";
import type { AnnotationEditorInitialState } from "../../src/webviews/shared/types";

const initial: AnnotationEditorInitialState = {
  imagePath: "/tmp/image.png",
  imageUri: "vscode-webview-resource:/image.png",
  classNames: ["person"],
  initialBoxes: [],
  initialError: null,
};

describe("annotation editor webview security", () => {
  it("allows the existing VS Code resource URI and inert raster data URLs", () => {
    expect(sanitizeImageUri(" vscode-webview-resource:/image.png ")).toBe(initial.imageUri);
    expect(sanitizeImageUri("data:image/png;base64,AAAA")).toBe("data:image/png;base64,AAAA");
  });

  it.each([
    "javascript:alert(1)",
    "https://example.invalid/malicious.png",
    "data:text/html;base64,PHNjcmlwdD4=",
    "data:image/svg+xml;base64,PHN2Zz4=",
    "vscode-webview-resource:/image.png\n<script>",
    null,
    { toString: () => "data:image/png;base64,AAAA" },
  ])("blocks untrusted image URI %s", (input) => {
    expect(sanitizeImageUri(input)).toBe("");
  });

  it("sanitizes the initial state before rendering the image", () => {
    expect(
      sanitizeAnnotationEditorState({ ...initial, imageUri: "javascript:alert(1)" }, initial)
        ?.imageUri
    ).toBe("");
  });

  it("falls back on malformed initial state", () => {
    expect(sanitizeAnnotationEditorState({ ...initial, initialBoxes: "bad" }, initial)).toBe(
      initial
    );
    expect(sanitizeAnnotationEditorState(null, initial)).toBe(initial);
  });

  it("rejects malformed queue metadata instead of copying untrusted fields", () => {
    expect(sanitizeAnnotationEditorState({ ...initial, isQueueMode: "true" }, initial)).toBe(
      initial
    );
    expect(
      sanitizeAnnotationEditorState({ ...initial, queueScore: Number.POSITIVE_INFINITY }, initial)
    ).toBe(initial);
    expect(
      sanitizeAnnotationEditorState(
        {
          ...initial,
          initialBoxes: [{ classId: 0, className: "person", x: "bad", y: 0, width: 1, height: 1 }],
        },
        initial
      )
    ).toBe(initial);
  });

  it("preserves validated queue metadata but strips unknown fields", () => {
    const state = sanitizeAnnotationEditorState({
      ...initial,
      isQueueMode: true,
      queueReason: "review",
      queueScore: 0.5,
      queueEntryId: "entry_1",
      datasetPath: "/tmp/dataset",
      unexpectedProperty: "must not reach the UI",
    });
    expect(state).toMatchObject({
      ...initial,
      isQueueMode: true,
      queueReason: "review",
      queueScore: 0.5,
      queueEntryId: "entry_1",
      datasetPath: "/tmp/dataset",
    });
    expect(state).not.toHaveProperty("unexpectedProperty");
  });

  it("accepts valid extension updates from the webview origin", () => {
    const event = {
      origin: "vscode-webview://trusted",
      data: {
        type: "setEditorState",
        state: { ...initial, imageUri: "data:image/webp;base64,AAAA" },
      },
    };
    expect(readTrustedEditorMessage(event, event.origin)?.imageUri).toBe(
      "data:image/webp;base64,AAAA"
    );
  });

  it("blocks cross-origin, malformed, and unrelated messages", () => {
    const valid = { type: "setEditorState", state: initial };
    expect(
      readTrustedEditorMessage(
        { origin: "https://attacker.invalid", data: valid },
        "vscode-webview://trusted"
      )
    ).toBeNull();
    expect(
      readTrustedEditorMessage(
        { origin: "vscode-webview://trusted", data: { type: "setEditorState", state: [] } },
        "vscode-webview://trusted"
      )
    ).toBeNull();
    expect(
      readTrustedEditorMessage(
        { origin: "vscode-webview://trusted", data: { type: "other", state: initial } },
        "vscode-webview://trusted"
      )
    ).toBeNull();
  });
});

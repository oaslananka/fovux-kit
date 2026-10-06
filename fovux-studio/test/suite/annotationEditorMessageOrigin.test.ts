import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import type { AnnotationEditorInitialState } from "../../src/webviews/shared/types";

const mockWindow = {
  location: { origin: "https://test.vscode-webview.net" },
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
};

vi.stubGlobal("window", mockWindow);
vi.stubGlobal(
  "MessageEvent",
  class MessageEvent extends Event {
    data: unknown;
    origin: string;
    constructor(type: string, init: { data?: unknown; origin?: string } = {}) {
      super(type);
      this.data = init.data;
      this.origin = init.origin || "";
    }
  }
);

describe("annotation editor message origin validation", () => {
  let originalLocation: { origin: string };
  let mockSetEditorState: ReturnType<typeof vi.fn>;
  let trustedOrigin: string;

  beforeEach(() => {
    originalLocation = mockWindow.location;
    trustedOrigin = "https://test.vscode-webview.net";
    mockSetEditorState = vi.fn();

    mockWindow.location = { origin: trustedOrigin };
  });

  afterEach(() => {
    mockWindow.location = originalLocation;
    vi.restoreAllMocks();
  });

  function createMessageEvent(data: unknown, origin: string = trustedOrigin): MessageEvent {
    return new (globalThis.MessageEvent as unknown as new (
      type: string,
      init: { data?: unknown; origin?: string }
    ) => MessageEvent)("message", { data, origin });
  }

  function sanitizeImageUri(uri: unknown): string {
    if (typeof uri !== "string") {
      return "";
    }
    const value = uri.trim();
    if (!value) {
      return "";
    }
    if (value.startsWith("vscode-webview-resource:")) {
      return value;
    }
    if (/^data:image\/[a-zA-Z0-9.+-]+;base64,[a-zA-Z0-9+/=]+$/.test(value)) {
      return value;
    }
    return "";
  }

  function handleMessageEvent(
    event: MessageEvent,
    setEditorState: (state: AnnotationEditorInitialState) => void
  ): void {
    if (event.origin !== window.location.origin) {
      return;
    }
    const message = event.data;
    if (!message || message.type !== "setEditorState" || !message.state) {
      return;
    }
    const nextState = message.state as AnnotationEditorInitialState;
    if (typeof nextState !== "object" || nextState === null || Array.isArray(nextState)) {
      return;
    }

    setEditorState({
      ...nextState,
      imageUri: sanitizeImageUri(nextState.imageUri),
    });
  }

  it("accepts messages from trusted origin", () => {
    const validState: AnnotationEditorInitialState = {
      imagePath: "/test/image.jpg",
      imageUri: "vscode-webview-resource:/test/image.jpg",
      classNames: ["class_0"],
      initialBoxes: [],
      initialError: null,
    };

    const event = createMessageEvent({
      type: "setEditorState",
      state: validState,
    });

    handleMessageEvent(event, mockSetEditorState);

    expect(mockSetEditorState).toHaveBeenCalledWith({
      ...validState,
      imageUri: sanitizeImageUri(validState.imageUri),
    });
  });

  describe.each([
    ["untrusted origin", "https://evil.com"],
    ["null origin", "null"],
    ["empty origin", ""],
  ])("rejects messages from %s", (_, origin) => {
    it("does not call setEditorState", () => {
      const validState: AnnotationEditorInitialState = {
        imagePath: "/test/image.jpg",
        imageUri: "vscode-webview-resource:/test/image.jpg",
        classNames: ["class_0"],
        initialBoxes: [],
        initialError: null,
      };

      const event = createMessageEvent(
        {
          type: "setEditorState",
          state: validState,
        },
        origin
      );

      handleMessageEvent(event, mockSetEditorState);

      expect(mockSetEditorState).not.toHaveBeenCalled();
    });
  });

  it("rejects messages with wrong type", () => {
    const event = createMessageEvent({
      type: "otherType",
      state: { imagePath: "", imageUri: "", classNames: [], initialBoxes: [], initialError: null },
    });

    handleMessageEvent(event, mockSetEditorState);

    expect(mockSetEditorState).not.toHaveBeenCalled();
  });

  it("rejects messages with missing state", () => {
    const event = createMessageEvent({
      type: "setEditorState",
    });

    handleMessageEvent(event, mockSetEditorState);

    expect(mockSetEditorState).not.toHaveBeenCalled();
  });

  it("rejects messages with null data", () => {
    const event = createMessageEvent(null);

    handleMessageEvent(event, mockSetEditorState);

    expect(mockSetEditorState).not.toHaveBeenCalled();
  });

  it("rejects messages with undefined data", () => {
    const event = createMessageEvent(undefined);

    handleMessageEvent(event, mockSetEditorState);

    expect(mockSetEditorState).not.toHaveBeenCalled();
  });

  it("sanitizes imageUri in accepted state", () => {
    const stateWithBadUri: AnnotationEditorInitialState = {
      imagePath: "/test/image.jpg",
      imageUri: "javascript:alert(1)",
      classNames: ["class_0"],
      initialBoxes: [],
      initialError: null,
    };

    const event = createMessageEvent({
      type: "setEditorState",
      state: stateWithBadUri,
    });

    handleMessageEvent(event, mockSetEditorState);

    expect(mockSetEditorState).toHaveBeenCalledWith({
      ...stateWithBadUri,
      imageUri: "",
    });
  });

  it("accepts valid vscode-webview-resource imageUri", () => {
    const stateWithValidUri: AnnotationEditorInitialState = {
      imagePath: "/test/image.jpg",
      imageUri: "vscode-webview-resource:/test/image.jpg",
      classNames: ["class_0"],
      initialBoxes: [],
      initialError: null,
    };

    const event = createMessageEvent({
      type: "setEditorState",
      state: stateWithValidUri,
    });

    handleMessageEvent(event, mockSetEditorState);

    expect(mockSetEditorState).toHaveBeenCalledWith({
      ...stateWithValidUri,
      imageUri: "vscode-webview-resource:/test/image.jpg",
    });
  });

  it("accepts valid data URI imageUri", () => {
    const stateWithDataUri: AnnotationEditorInitialState = {
      imagePath: "/test/image.jpg",
      imageUri:
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
      classNames: ["class_0"],
      initialBoxes: [],
      initialError: null,
    };

    const event = createMessageEvent({
      type: "setEditorState",
      state: stateWithDataUri,
    });

    handleMessageEvent(event, mockSetEditorState);

    expect(mockSetEditorState).toHaveBeenCalledWith({
      ...stateWithDataUri,
      imageUri: stateWithDataUri.imageUri,
    });
  });

  it("handles malformed state data gracefully", () => {
    const event = createMessageEvent({
      type: "setEditorState",
      state: "not an object",
    });

    handleMessageEvent(event, mockSetEditorState);

    expect(mockSetEditorState).not.toHaveBeenCalled();
  });

  it("handles state with missing required fields", () => {
    const event = createMessageEvent({
      type: "setEditorState",
      state: { imagePath: "/test.jpg" },
    });

    handleMessageEvent(event, mockSetEditorState);

    expect(mockSetEditorState).toHaveBeenCalled();
    const calledState = mockSetEditorState.mock.calls[0][0];
    expect(calledState.imagePath).toBe("/test.jpg");
  });
});

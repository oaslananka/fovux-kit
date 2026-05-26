import { vi } from "vitest";

export const registeredCommands: string[] = [];
export const registeredCommandHandlers = new Map<
  string,
  (...args: unknown[]) => unknown
>();
export const createdPanels: Array<{
  id: string;
  title: string;
  options: Record<string, unknown>;
  panel: { webview: MockWebview };
}> = [];
export const createdTreeViews: Array<{
  id: string;
  options: Record<string, unknown>;
  view: MockTreeView;
}> = [];
export const registeredFileDecorationProviders: unknown[] = [];
export const registeredCodeLensProviders: Array<{
  selector: unknown;
  provider: unknown;
}> = [];
let workspaceTrusted = true;

type MockWebview = {
  html: string;
  cspSource: string;
  asWebviewUri: (uri: { path?: string; fsPath?: string }) => {
    toString: () => string;
  };
  onDidReceiveMessage: ReturnType<typeof vi.fn>;
  postMessage: ReturnType<typeof vi.fn>;
};

type MockTreeView = {
  badge?: { value: number; tooltip: string };
  message?: string;
  dispose: ReturnType<typeof vi.fn>;
};

export function resetVscodeMockState(): void {
  registeredCommands.length = 0;
  registeredCommandHandlers.clear();
  createdPanels.length = 0;
  createdTreeViews.length = 0;
  registeredFileDecorationProviders.length = 0;
  registeredCodeLensProviders.length = 0;
  workspaceTrusted = true;
  mockGlobalState.storage.clear();
  mockGlobalState.get.mockClear();
  mockGlobalState.update.mockClear();
}

export function setWorkspaceTrust(isTrusted: boolean): void {
  workspaceTrusted = isTrusted;
}

export const mockGlobalState = {
  storage: new Map<string, unknown>(),
  get: vi.fn((key: string, defaultValue?: unknown) =>
    mockGlobalState.storage.has(key)
      ? mockGlobalState.storage.get(key)
      : defaultValue,
  ),
  update: vi.fn((key: string, value: unknown) => {
    mockGlobalState.storage.set(key, value);
    return Promise.resolve();
  }),
};

vi.mock("vscode", () => {
  class EventEmitter<T> {
    readonly event = vi.fn();
    fire = vi.fn((_value?: T) => undefined);
    dispose = vi.fn();
  }

  class TreeItem {
    label: string;
    collapsibleState: number;
    tooltip?: string;
    description?: string;
    iconPath?: unknown;
    contextValue?: string;
    command?: unknown;

    constructor(label: string, collapsibleState = 0) {
      this.label = label;
      this.collapsibleState = collapsibleState;
    }
  }

  class ThemeIcon {
    constructor(
      readonly id: string,
      readonly color?: unknown,
    ) {}
  }

  class ThemeColor {
    constructor(readonly id: string) {}
  }

  class Range {
    constructor(
      readonly startLine: number,
      readonly startCharacter: number,
      readonly endLine: number,
      readonly endCharacter: number,
    ) {}
  }

  class CodeLens {
    constructor(
      readonly range: Range,
      readonly command?: unknown,
    ) {}
  }

  class FileDecoration {
    constructor(
      readonly badge?: string,
      readonly tooltip?: string,
      readonly color?: unknown,
    ) {}
  }

  const createWebviewPanel = vi.fn(
    (
      id: string,
      title: string,
      _column: number,
      options: Record<string, unknown>,
    ) => {
      const webview: MockWebview = {
        html: "",
        cspSource: "vscode-webview-resource",
        asWebviewUri: (uri) => ({
          toString: () => `vscode-resource:${uri.path ?? uri.fsPath ?? ""}`,
        }),
        onDidReceiveMessage: vi.fn(),
        postMessage: vi.fn(() => Promise.resolve(true)),
      };
      const panel = { webview };
      createdPanels.push({ id, title, options, panel });
      return panel;
    },
  );

  const createTreeView = vi.fn(
    (id: string, options: Record<string, unknown>) => {
      const view: MockTreeView = {
        badge: undefined,
        message: undefined,
        dispose: vi.fn(),
      };
      createdTreeViews.push({ id, options, view });
      return view;
    },
  );

  const configuration = {
    get: vi.fn((key: string) => {
      if (key === "httpPort") return 7823;
      if (key === "pollIntervalMs") return 2000;
      if (key === "home") return "";
      if (key === "profiles") return [];
      if (key === "activeProfile") return "";
      return undefined;
    }),
    update: vi.fn(() => Promise.resolve()),
  };

  return {
    window: {
      createWebviewPanel,
      createTreeView,
      createOutputChannel: vi.fn(() => ({
        appendLine: vi.fn(),
        dispose: vi.fn(),
      })),
      createStatusBarItem: vi.fn(() => ({
        text: "",
        tooltip: "",
        command: undefined,
        show: vi.fn(),
        hide: vi.fn(),
        dispose: vi.fn(),
      })),
      registerFileDecorationProvider: vi.fn((provider: unknown) => {
        registeredFileDecorationProviders.push(provider);
        return { dispose: vi.fn() };
      }),
      showOpenDialog: vi.fn(),
      showInformationMessage: vi.fn(),
      showWarningMessage: vi.fn(),
      showErrorMessage: vi.fn(),
      showInputBox: vi.fn(),
      showQuickPick: vi.fn(),
    },
    commands: {
      registerCommand: vi.fn(
        (commandId: string, handler: (...args: unknown[]) => unknown) => {
          registeredCommands.push(commandId);
          registeredCommandHandlers.set(commandId, handler);
          return { dispose: vi.fn() };
        },
      ),
      executeCommand: vi.fn(),
    },
    workspace: {
      getConfiguration: vi.fn(() => configuration),
      workspaceFolders: [
        { uri: { fsPath: process.cwd(), path: process.cwd() } },
      ],
      get isTrusted() {
        return workspaceTrusted;
      },
      createFileSystemWatcher: vi.fn(() => ({
        onDidChange: vi.fn(),
        onDidCreate: vi.fn(),
        onDidDelete: vi.fn(),
        dispose: vi.fn(),
      })),
      onDidChangeConfiguration: vi.fn(() => ({ dispose: vi.fn() })),
    },
    languages: {
      registerCodeLensProvider: vi.fn(
        (selector: unknown, provider: unknown) => {
          registeredCodeLensProviders.push({ selector, provider });
          return { dispose: vi.fn() };
        },
      ),
    },
    ViewColumn: { One: 1 },
    ConfigurationTarget: { Workspace: 2 },
    TreeItemCollapsibleState: { None: 0, Expanded: 2 },
    StatusBarAlignment: { Left: 1, Right: 2 },
    ThemeIcon,
    ThemeColor,
    Range,
    CodeLens,
    FileDecoration,
    TreeItem,
    EventEmitter,
    Uri: {
      file: (fsPath: string) => ({ fsPath, path: fsPath }),
      joinPath: (
        base: { path?: string; fsPath?: string },
        ...parts: string[]
      ) => ({
        path: [base.path ?? base.fsPath ?? "", ...parts].join("/"),
      }),
    },
    env: {
      clipboard: {
        writeText: vi.fn(),
      },
    },
    lm: undefined,
  };
});

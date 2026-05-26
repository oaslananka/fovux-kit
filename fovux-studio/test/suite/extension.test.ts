import * as fs from "fs";
import * as os from "os";
import * as path from "path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "./helpers/vscodeMock";
import { activate } from "../../src/extension";
import { openCompareRuns } from "../../src/commands/compareRuns";
import { openDashboard } from "../../src/commands/openDashboard";
import { openExportWizard } from "../../src/commands/openExportWizard";
import { openTrainingLauncher } from "../../src/commands/openTrainingLauncher";
import { copyRunId } from "../../src/commands/runActions";
import {
  createdPanels,
  createdTreeViews,
  registeredCodeLensProviders,
  registeredCommandHandlers,
  registeredCommands,
  registeredFileDecorationProviders,
  resetVscodeMockState,
} from "./helpers/vscodeMock";
import { ExportsTreeProvider } from "../../src/views/exportsTree";
import { ModelsTreeProvider } from "../../src/views/modelsTree";
import { RunsTreeProvider } from "../../src/views/runsTree";

describe("Fovux Studio extension", () => {
  let tempHome: string | undefined;

  beforeEach(() => {
    resetVscodeMockState();
    vi.resetModules();
    delete process.env["FOVUX_HOME"];
    tempHome = undefined;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    if (tempHome) {
      fs.rmSync(tempHome, { recursive: true, force: true });
    }
  });

  it("registers all user-facing commands on activate", async () => {
    const context = {
      extensionUri: { path: "/extension" },
      subscriptions: [] as Array<unknown>,
    };
    activate(context as never);

    expect(registeredCommands).toEqual(
      expect.arrayContaining([
        "fovux.startTraining",
        "fovux.startServer",
        "fovux.stopServer",
        "fovux.openDashboard",
        "fovux.openTimeline",
        "fovux.openDatasetInspector",
        "fovux.openAnnotationEditor",
        "fovux.openExportWizard",
        "fovux.compareRuns",
        "fovux.openRunInExplorer",
        "fovux.revealPath",
        "fovux.deleteRun",
        "fovux.tagRun",
        "fovux.selectProfile",
        "fovux.installBackend",
        "fovux.runDoctor",
        "fovux.openUpgradeGuide",
        "fovux.openSecurityDoc",
        "fovux.validateDataset",
        "fovux.refreshDoctor",
        "fovux.fixDoctorCheck",
      ]),
    );
    expect(createdTreeViews.map((entry) => entry.id)).toEqual(
      expect.arrayContaining([
        "fovux.runsView",
        "fovux.modelsView",
        "fovux.exportsView",
        "fovux.doctorView",
      ]),
    );
    expect(registeredFileDecorationProviders).toHaveLength(1);
    expect(registeredCodeLensProviders).toHaveLength(1);
  });

  it("creates a script-enabled dashboard webview", async () => {
    const context = {
      extensionUri: { path: "/extension" },
      subscriptions: [] as Array<unknown>,
    };
    tempHome = fs.mkdtempSync(path.join(os.tmpdir(), "fovux-dashboard-auth-"));
    process.env["FOVUX_HOME"] = tempHome;
    fs.writeFileSync(path.join(tempHome, "auth.token"), "secret-token\n");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/health")) {
          return { ok: true };
        }
        if (url.endsWith("/runs")) {
          return {
            ok: true,
            json: async () => [],
          };
        }
        return { ok: false, status: 404, statusText: "Not Found" };
      }),
    );

    await openDashboard(context as never);

    expect(createdPanels).toHaveLength(1);
    expect(createdPanels[0]?.options["enableScripts"]).toBe(true);
    expect(createdPanels[0]?.options["localResourceRoots"]).toEqual([
      { path: "/extension" },
    ]);
    expect(createdPanels[0]?.panel.webview.html).toContain(
      "webviews/dashboard/main.js",
    );
  });

  it("sets local resource roots for all script-enabled webviews", async () => {
    const context = {
      extensionUri: { path: "/extension" },
      subscriptions: [] as Array<unknown>,
    };
    tempHome = fs.mkdtempSync(path.join(os.tmpdir(), "fovux-webviews-auth-"));
    process.env["FOVUX_HOME"] = tempHome;
    fs.writeFileSync(path.join(tempHome, "auth.token"), "secret-token\n");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 503, statusText: "Offline" })),
    );

    await openDashboard(context as never);
    await openExportWizard(context as never);
    await openCompareRuns(context as never);
    await openTrainingLauncher(context as never);

    expect(createdPanels).toHaveLength(4);
    for (const panel of createdPanels) {
      expect(panel.options["enableScripts"]).toBe(true);
      expect(panel.options["localResourceRoots"]).toEqual([
        { path: "/extension" },
      ]);
    }
  });

  it("lists run directories in the runs tree provider", () => {
    tempHome = fs.mkdtempSync(path.join(os.tmpdir(), "fovux-tmp-runs-"));
    process.env["FOVUX_HOME"] = tempHome;
    const runDir = path.join(tempHome, "runs", "run_demo");
    fs.mkdirSync(runDir, { recursive: true });
    fs.writeFileSync(
      path.join(runDir, "status.json"),
      JSON.stringify({ status: "running", current_epoch: 1, total_epochs: 5 }),
    );

    const provider = new RunsTreeProvider();
    const groups = provider.getChildren();
    const items = groups.length > 0 ? provider.getChildren(groups[0]) : [];

    expect(items).toHaveLength(1);
    expect(items[0]?.label).toBe("run_demo");
  });

  it("shows an error when copying a run ID fails", async () => {
    const vscode = await import("vscode");
    vi.mocked(vscode.env.clipboard.writeText).mockRejectedValueOnce(
      new Error("clipboard denied"),
    );

    await copyRunId({ runId: "run_demo" } as never);

    expect(vscode.window.showErrorMessage).toHaveBeenCalledWith(
      "Could not copy run_demo: clipboard denied",
    );
  });

  it("declares revealPath as a contributed command", () => {
    const packageJson = JSON.parse(
      fs.readFileSync(path.join(process.cwd(), "package.json"), "utf8"),
    );
    const commands = packageJson.contributes.commands as Array<{
      command: string;
      enablement?: string;
    }>;
    const contributedIds = commands.map((command) => command.command);

    expect(contributedIds).toEqual(
      expect.arrayContaining([
        "fovux.revealPath",
        "fovux.installBackend",
        "fovux.runDoctor",
        "fovux.openUpgradeGuide",
        "fovux.openSecurityDoc",
        "fovux.validateDataset",
      ]),
    );
    expect(
      commands.find((command) => command.command === "fovux.revealPath")
        ?.enablement,
    ).toBeUndefined();
    expect(packageJson.capabilities.untrustedWorkspaces.supported).toBe(
      "limited",
    );
    expect(packageJson.contributes.keybindings).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ command: "fovux.startTraining" }),
        expect.objectContaining({ command: "fovux.openDashboard" }),
      ]),
    );
  });

  it("refreshes runs, models, and exports from refreshViews", () => {
    const context = {
      extensionUri: { path: "/extension" },
      subscriptions: [] as Array<unknown>,
    };
    const runsRefresh = vi.spyOn(RunsTreeProvider.prototype, "refresh");
    const modelsRefresh = vi.spyOn(ModelsTreeProvider.prototype, "refresh");
    const exportsRefresh = vi.spyOn(ExportsTreeProvider.prototype, "refresh");
    activate(context as never);

    registeredCommandHandlers.get("fovux.refreshViews")?.();

    expect(runsRefresh).toHaveBeenCalled();
    expect(modelsRefresh).toHaveBeenCalled();
    expect(exportsRefresh).toHaveBeenCalled();
  });
});

/**
 * Fovux Studio — VS Code extension entry point.
 *
 * Activates the Fovux activity bar, registers commands, and starts
 * the run directory watcher.
 */

import * as vscode from "vscode";
import { DataYamlCodeLensProvider } from "./codelens/dataYamlCodeLens";
import { openCompareRuns } from "./commands/compareRuns";
import { openAnnotationEditor } from "./commands/openAnnotationEditor";
import { openDashboard } from "./commands/openDashboard";
import { openDatasetInspector } from "./commands/openDatasetInspector";
import { openExportWizard } from "./commands/openExportWizard";
import { openTimeline } from "./commands/openTimeline";
import { openTrainingLauncher } from "./commands/openTrainingLauncher";
import {
  copyRunId,
  deleteRun,
  resumeRun,
  stopRun,
  tagRun,
} from "./commands/runActions";
import { registerWalkthroughCommands } from "./commands/walkthroughActions";
import { RunFileDecorationProvider } from "./decorations/runFileDecorator";
import { ExtensionFovuxClient } from "./fovux/extensionClient";
import { registerFovuxLanguageModelTool } from "./fovux/languageModelTools";
import {
  getSessionActiveFovuxProfile,
  resolveFovuxHome,
  resolveFovuxProfiles,
  setSessionActiveFovuxProfile,
} from "./fovux/paths";
import {
  disposeFovuxServerManager,
  startFovuxServer,
  stopFovuxServer,
} from "./fovux/serverManager";
import { logger } from "./util/logger";
import {
  disposeStatusBarItems,
  showPrivacyBadge,
  updateActiveRunsBadge,
  updateProfileStatusBar,
} from "./util/statusBar";
import { DoctorTreeProvider } from "./views/doctorTree";
import { ExportsSummary, ExportsTreeProvider } from "./views/exportsTree";
import { ModelsSummary, ModelsTreeProvider } from "./views/modelsTree";
import { RunsSummary, RunsTreeProvider } from "./views/runsTree";

export function activate(context: vscode.ExtensionContext): void {
  logger.info("Fovux Studio activating...");
  registerFovuxLanguageModelTool(context);
  registerWalkthroughCommands(context);
  showPrivacyBadge();
  updateProfileStatusBar(getSessionActiveFovuxProfile() ?? "default");

  const runsProvider = new RunsTreeProvider();
  const modelsProvider = new ModelsTreeProvider();
  const exportsProvider = new ExportsTreeProvider();
  const doctorProvider = new DoctorTreeProvider();
  const runDecorations = new RunFileDecorationProvider();
  const runsView = vscode.window.createTreeView("fovux.runsView", {
    treeDataProvider: runsProvider,
    showCollapseAll: true,
  });
  const modelsView = vscode.window.createTreeView("fovux.modelsView", {
    treeDataProvider: modelsProvider,
    showCollapseAll: true,
  });
  const exportsView = vscode.window.createTreeView("fovux.exportsView", {
    treeDataProvider: exportsProvider,
    showCollapseAll: false,
  });
  const doctorView = vscode.window.createTreeView("fovux.doctorView", {
    treeDataProvider: doctorProvider,
    showCollapseAll: true,
  });

  const syncViews = (): void => {
    syncRunsView(runsView, runsProvider.getSummary());
    runDecorations.update(runsProvider.getRunDecorations());
    syncModelsView(modelsView, modelsProvider.getSummary());
    syncExportsView(exportsView, exportsProvider.getSummary());
  };

  syncViews();
  context.subscriptions.push(runsProvider.onDidChangeTreeData(syncViews));
  context.subscriptions.push(modelsProvider.onDidChangeTreeData(syncViews));
  context.subscriptions.push(exportsProvider.onDidChangeTreeData(syncViews));

  context.subscriptions.push(
    runsProvider,
    modelsProvider,
    exportsProvider,
    doctorProvider,
    runDecorations,
    runsView,
    modelsView,
    exportsView,
    doctorView,
    vscode.window.registerFileDecorationProvider(runDecorations),
    vscode.languages.registerCodeLensProvider(
      { pattern: "**/data.yaml", scheme: "file" },
      new DataYamlCodeLensProvider(),
    ),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("fovux.startServer", () =>
      startFovuxServer(),
    ),
    vscode.commands.registerCommand("fovux.stopServer", () =>
      stopFovuxServer(),
    ),
    vscode.commands.registerCommand(
      "fovux.startTraining",
      (datasetPath?: string) => {
        if (!vscode.workspace.isTrusted) {
          void vscode.window.showErrorMessage(
            "Fovux training cannot start in an untrusted workspace. Trust this workspace first.",
          );
          return;
        }
        return openTrainingLauncher(
          context,
          typeof datasetPath === "string" ? datasetPath : "",
        );
      },
    ),
    vscode.commands.registerCommand("fovux.openDashboard", () =>
      openDashboard(context),
    ),
    vscode.commands.registerCommand(
      "fovux.openDatasetInspector",
      (datasetPath?: string) =>
        openDatasetInspector(
          context,
          typeof datasetPath === "string" ? datasetPath : undefined,
        ),
    ),
    vscode.commands.registerCommand("fovux.openAnnotationEditor", () =>
      openAnnotationEditor(context),
    ),
    vscode.commands.registerCommand("fovux.openExportWizard", () =>
      openExportWizard(context),
    ),
    vscode.commands.registerCommand("fovux.openTimeline", () =>
      openTimeline(context),
    ),
    vscode.commands.registerCommand("fovux.compareRuns", () =>
      openCompareRuns(context),
    ),
    vscode.commands.registerCommand(
      "fovux.openRunInExplorer",
      (target: string | { runPath?: string }) => {
        const runPath = typeof target === "string" ? target : target?.runPath;
        if (runPath) {
          void vscode.commands.executeCommand(
            "revealFileInOS",
            vscode.Uri.file(runPath),
          );
        }
      },
    ),
    vscode.commands.registerCommand("fovux.stopRun", (item) => stopRun(item)),
    vscode.commands.registerCommand("fovux.resumeRun", (item) =>
      resumeRun(item),
    ),
    vscode.commands.registerCommand("fovux.copyRunId", (item) =>
      copyRunId(item),
    ),
    vscode.commands.registerCommand("fovux.deleteRun", (item) =>
      deleteRun(item),
    ),
    vscode.commands.registerCommand("fovux.tagRun", (item) => tagRun(item)),
    vscode.commands.registerCommand(
      "fovux.revealPath",
      (targetPath: string) => {
        void vscode.commands.executeCommand(
          "revealFileInOS",
          vscode.Uri.file(targetPath),
        );
      },
    ),
    vscode.commands.registerCommand("fovux.openFovuxHome", () => {
      void vscode.commands.executeCommand(
        "revealFileInOS",
        vscode.Uri.file(resolveFovuxHome()),
      );
    }),
    vscode.commands.registerCommand("fovux.selectProfile", async () => {
      const profiles = resolveFovuxProfiles();
      if (!profiles.length) {
        void vscode.window.showInformationMessage(
          "No Fovux profiles are configured.",
        );
        return;
      }
      const picked = await vscode.window.showQuickPick(
        profiles.map((profile) => ({
          label: profile.name,
          description: profile.home,
        })),
        { placeHolder: "Select FOVUX_HOME profile" },
      );
      if (!picked) {
        return;
      }
      setSessionActiveFovuxProfile(picked.label);
      updateProfileStatusBar(picked.label);
      runsProvider.reconfigure();
      modelsProvider.reconfigure();
      exportsProvider.reconfigure();
      syncViews();
    }),
    vscode.commands.registerCommand(
      "fovux.validateDataset",
      async (datasetPath?: string) => {
        const target =
          typeof datasetPath === "string" ? datasetPath : undefined;
        if (!target) {
          void openDatasetInspector(context);
          return;
        }
        try {
          const client = await ExtensionFovuxClient.create();
          const result = await client.invokeTool<{ summary?: string }>(
            "dataset_validate",
            {
              dataset_path: target,
            },
          );
          void vscode.window.showInformationMessage(
            result.summary ?? "Dataset validation completed.",
          );
        } catch (error) {
          void vscode.window.showErrorMessage(
            error instanceof Error ? error.message : String(error),
          );
        }
      },
    ),
    vscode.commands.registerCommand("fovux.refreshDoctor", () =>
      doctorProvider.refresh(),
    ),
    vscode.commands.registerCommand("fovux.fixDoctorCheck", (item) =>
      doctorProvider.fixCheck(item),
    ),
    vscode.commands.registerCommand("fovux.refreshViews", () => {
      runsProvider.refresh();
      modelsProvider.refresh();
      exportsProvider.refresh();
      void doctorProvider.refresh();
      syncViews();
    }),
  );

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (!event.affectsConfiguration("fovux")) {
        return;
      }
      runsProvider.reconfigure();
      modelsProvider.reconfigure();
      exportsProvider.reconfigure();
      syncViews();
    }),
  );

  logger.info("Fovux Studio activated.");
  void doctorProvider.refresh();
}

export function deactivate(): void {
  disposeFovuxServerManager();
  disposeStatusBarItems();
  logger.info("Fovux Studio deactivated.");
}

function syncRunsView(
  view: vscode.TreeView<unknown>,
  summary: RunsSummary,
): void {
  view.badge =
    summary.totalRuns > 0
      ? { value: summary.totalRuns, tooltip: "Tracked runs" }
      : undefined;

  if (summary.totalRuns === 0) {
    view.message = `Watching ${summary.home}. No runs detected yet.`;
    updateActiveRunsBadge(0);
    return;
  }

  const parts = [
    summary.counts.running ? `${summary.counts.running} running` : "",
    summary.counts.complete ? `${summary.counts.complete} complete` : "",
    summary.counts.failed ? `${summary.counts.failed} failed` : "",
  ].filter((part) => part !== "");

  view.message = `${parts.join(" · ")} · ${summary.home}`;
  updateActiveRunsBadge(summary.activeRuns, summary.latestMap50);
}

function syncModelsView(
  view: vscode.TreeView<unknown>,
  summary: ModelsSummary,
): void {
  view.badge =
    summary.totalModels > 0
      ? { value: summary.totalModels, tooltip: "Indexed model artifacts" }
      : undefined;

  if (summary.totalModels === 0) {
    view.message = `Looking in ${summary.home}. No checkpoints or exports yet.`;
    return;
  }

  const parts = [
    summary.counts.checkpoints
      ? `${summary.counts.checkpoints} checkpoints`
      : "",
    summary.counts.exports ? `${summary.counts.exports} exports` : "",
    summary.counts.library ? `${summary.counts.library} library` : "",
  ].filter((part) => part !== "");

  view.message = `${parts.join(" · ")} · ${summary.home}`;
}

function syncExportsView(
  view: vscode.TreeView<unknown>,
  summary: ExportsSummary,
): void {
  view.badge =
    summary.totalExports > 0
      ? { value: summary.totalExports, tooltip: "Recorded exports" }
      : undefined;

  if (summary.totalExports === 0) {
    view.message = `Watching ${summary.home}. No export history yet.`;
    return;
  }

  view.message = `${summary.totalExports} exports · ${summary.home}`;
}

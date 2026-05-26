import * as vscode from "vscode";

import { ExtensionFovuxClient } from "../fovux/extensionClient";
import { RunItem } from "../views/runsTree";

export async function stopRun(target: RunItem | undefined): Promise<void> {
  const run = target;
  if (!run) {
    void vscode.window.showWarningMessage("Select a run before stopping it.");
    return;
  }

  const client = await ExtensionFovuxClient.create();
  try {
    const result = await client.invokeTool<{ message?: string }>("train_stop", {
      run_id: run.runId,
      force: false,
      confirm: true,
    });
    void vscode.window.showInformationMessage(result.message ?? `Stopped ${run.runId}.`);
    void vscode.commands.executeCommand("fovux.refreshViews");
  } catch (error) {
    void vscode.window.showErrorMessage(
      `Could not stop ${run.runId}: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

export async function resumeRun(target: RunItem | undefined): Promise<void> {
  const run = target;
  if (!run) {
    void vscode.window.showWarningMessage("Select a run before resuming it.");
    return;
  }

  const client = await ExtensionFovuxClient.create();
  try {
    const result = await client.invokeTool<{ run_id: string }>("train_resume", {
      run_id: run.runId,
      confirm: true,
    });
    void vscode.window.showInformationMessage(`Resumed ${result.run_id}.`);
    void vscode.commands.executeCommand("fovux.refreshViews");
  } catch (error) {
    void vscode.window.showErrorMessage(
      `Could not resume ${run.runId}: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

export async function copyRunId(target: RunItem | undefined): Promise<void> {
  const run = target;
  if (!run) {
    void vscode.window.showWarningMessage("Select a run before copying its ID.");
    return;
  }

  try {
    await vscode.env.clipboard.writeText(run.runId);
    void vscode.window.showInformationMessage(`Copied run ID ${run.runId}.`);
  } catch (error) {
    void vscode.window.showErrorMessage(
      `Could not copy ${run.runId}: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

export async function deleteRun(target: RunItem | undefined): Promise<void> {
  const run = target;
  if (!run) {
    void vscode.window.showWarningMessage("Select a run before deleting it.");
    return;
  }

  const confirm = await vscode.window.showWarningMessage(
    `Delete ${run.runId} from Fovux? This removes the run directory and registry entry.`,
    { modal: true },
    "Delete"
  );
  if (confirm !== "Delete") {
    return;
  }

  const client = await ExtensionFovuxClient.create();
  try {
    await client.invokeTool("run_delete", {
      run_id: run.runId,
      delete_files: true,
      force: false,
      confirm: true,
    });
    void vscode.window.showInformationMessage(`Deleted ${run.runId}.`);
    void vscode.commands.executeCommand("fovux.refreshViews");
  } catch (error) {
    void vscode.window.showErrorMessage(
      `Could not delete ${run.runId}: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

export async function tagRun(target: RunItem | undefined): Promise<void> {
  const run = target;
  if (!run) {
    void vscode.window.showWarningMessage("Select a run before tagging it.");
    return;
  }

  const value = await vscode.window.showInputBox({
    title: `Tags for ${run.runId}`,
    prompt: "Comma-separated tags",
    placeHolder: "baseline, edge, int8",
  });
  if (value === undefined) {
    return;
  }

  const tags = value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
  const client = await ExtensionFovuxClient.create();
  try {
    await client.invokeTool("run_tag", { run_id: run.runId, tags, confirm: true });
    void vscode.window.showInformationMessage(`Updated tags for ${run.runId}.`);
    void vscode.commands.executeCommand("fovux.refreshViews");
  } catch (error) {
    void vscode.window.showErrorMessage(
      `Could not tag ${run.runId}: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

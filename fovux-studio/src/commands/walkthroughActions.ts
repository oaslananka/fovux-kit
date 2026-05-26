/**
 * Walkthrough step commands for the Fovux Studio Getting Started experience.
 */

import * as vscode from "vscode";

/**
 * Register commands used by walkthrough steps.
 */
export function registerWalkthroughCommands(
  context: vscode.ExtensionContext,
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("fovux.installBackend", async () => {
      const terminal = vscode.window.createTerminal({
        name: "Fovux Backend Install",
        message: "Installing fovux-mcp backend...",
      });
      if (process.platform === "win32") {
        terminal.sendText("uv tool install fovux-mcp");
      } else {
        terminal.sendText("uv tool install fovux-mcp");
      }
      terminal.show();
      void vscode.commands.executeCommand(
        "setContext",
        "fovux.walkthrough.backendInstalled",
        true,
      );
    }),

    vscode.commands.registerCommand("fovux.runDoctor", async () => {
      const terminal = vscode.window.createTerminal({
        name: "Fovux Doctor",
        message: "Running fovux doctor diagnostics...",
      });
      terminal.sendText("fovux-mcp doctor");
      terminal.show();
      void vscode.commands.executeCommand(
        "setContext",
        "fovux.walkthrough.doctorRan",
        true,
      );
    }),

    vscode.commands.registerCommand("fovux.openUpgradeGuide", async () => {
      const uri = vscode.Uri.parse(
        "https://oaslananka.github.io/fovux/upgrade/",
      );
      await vscode.env.openExternal(uri);
    }),

    vscode.commands.registerCommand("fovux.openSecurityDoc", async () => {
      // Open SECURITY.md from workspace if present, otherwise open on GitHub
      const files = await vscode.workspace.findFiles("SECURITY.md", null, 1);
      if (files.length > 0) {
        await vscode.window.showTextDocument(files[0]);
      } else {
        await vscode.env.openExternal(
          vscode.Uri.parse(
            "https://github.com/oaslananka/fovux/blob/main/SECURITY.md",
          ),
        );
      }
    }),
  );
}

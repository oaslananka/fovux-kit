import * as vscode from "vscode";

import {
  DashboardWebviewDiagnostics,
  getDashboardWebviewDiagnostics,
} from "../webviews/diagnostics";

export interface FovuxRuntimeState {
  workspaceTrusted: boolean;
  telemetryEnabled: false;
  extensionVersion: string;
  contributedCommands: string[];
}

export interface FovuxStudioApi {
  getRuntimeState(): FovuxRuntimeState;
  getDashboardDiagnostics(): DashboardWebviewDiagnostics;
}

interface CommandContribution {
  command?: unknown;
}

interface ExtensionPackageJson {
  version?: unknown;
  contributes?: {
    commands?: unknown;
  };
}

export function createFovuxStudioApi(context: vscode.ExtensionContext): FovuxStudioApi {
  return {
    getRuntimeState(): FovuxRuntimeState {
      const packageJson = context.extension.packageJSON as ExtensionPackageJson;
      return {
        workspaceTrusted: vscode.workspace.isTrusted,
        telemetryEnabled: false,
        extensionVersion: typeof packageJson.version === "string" ? packageJson.version : "unknown",
        contributedCommands: readContributedCommands(packageJson),
      };
    },
    getDashboardDiagnostics(): DashboardWebviewDiagnostics {
      return getDashboardWebviewDiagnostics();
    },
  };
}

function readContributedCommands(packageJson: ExtensionPackageJson): string[] {
  const commands = packageJson.contributes?.commands;
  if (!Array.isArray(commands)) {
    return [];
  }
  return commands.flatMap((entry: CommandContribution) =>
    typeof entry.command === "string" ? [entry.command] : []
  );
}

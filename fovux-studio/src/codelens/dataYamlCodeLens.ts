import * as path from "node:path";
import * as vscode from "vscode";

export class DataYamlCodeLensProvider implements vscode.CodeLensProvider {
  provideCodeLenses(document: vscode.TextDocument): vscode.CodeLens[] {
    if (!document.fileName.replace(/\\/g, "/").endsWith("/data.yaml")) {
      return [];
    }

    const topRange = new vscode.Range(0, 0, 0, 0);
    const datasetPath = path.dirname(document.uri.fsPath);

    return [
      new vscode.CodeLens(topRange, {
        title: "$(check) Validate Dataset",
        command: "fovux.validateDataset",
        arguments: [datasetPath],
      }),
      new vscode.CodeLens(topRange, {
        title: "$(search) Inspect Dataset",
        command: "fovux.openDatasetInspector",
        arguments: [datasetPath],
      }),
      new vscode.CodeLens(topRange, {
        title: "$(run) Start Training",
        command: "fovux.startTraining",
        arguments: [datasetPath],
      }),
    ];
  }
}

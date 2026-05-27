/**
 * Models TreeView provider.
 *
 * Lists checkpoints and exports under FOVUX_HOME/models, runs, and exports.
 */

import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

import { resolveFovuxHome } from "../fovux/paths";

type ModelTreeNode = ModelGroupItem | ModelItem;
type ModelGroupKey = "library" | "checkpoints" | "exports";

interface ModelRecord {
  label: string;
  filePath: string;
  sizeMb: number;
  detail: string;
  group: ModelGroupKey;
}

export interface ModelsSummary {
  home: string;
  totalModels: number;
  counts: Record<ModelGroupKey, number>;
}

const GROUP_LABELS: Record<ModelGroupKey, string> = {
  library: "Model Library",
  checkpoints: "Run Checkpoints",
  exports: "Exports",
};

class ModelGroupItem extends vscode.TreeItem {
  constructor(
    public readonly group: ModelGroupKey,
    public readonly items: ModelItem[]
  ) {
    super(GROUP_LABELS[group], vscode.TreeItemCollapsibleState.Expanded);
    this.description = `${items.length}`;
    this.iconPath = new vscode.ThemeIcon(group === "exports" ? "archive" : "package");
    this.contextValue = "fovuxModelGroup";
  }
}

export class ModelItem extends vscode.TreeItem {
  constructor(private readonly record: ModelRecord) {
    super(record.label, vscode.TreeItemCollapsibleState.None);
    this.tooltip = record.filePath;
    this.description = `${record.sizeMb.toFixed(1)} MB · ${record.detail}`;
    this.iconPath = new vscode.ThemeIcon(record.group === "exports" ? "archive" : "package");
    this.contextValue = "fovuxModel";
    this.command = {
      command: "fovux.revealPath",
      title: "Reveal in Explorer",
      arguments: [record.filePath],
    };
  }
}

export class ModelsTreeProvider
  implements vscode.TreeDataProvider<ModelTreeNode>, vscode.Disposable
{
  private readonly onDidChangeEmitter = new vscode.EventEmitter<ModelTreeNode | undefined | null>();
  readonly onDidChangeTreeData = this.onDidChangeEmitter.event;

  private watchers: vscode.FileSystemWatcher[] = [];

  constructor() {
    this.configureWatchers();
  }

  refresh(): void {
    this.onDidChangeEmitter.fire(undefined);
  }

  reconfigure(): void {
    this.disposeWatchers();
    this.configureWatchers();
    this.refresh();
  }

  getSummary(): ModelsSummary {
    const records = this.readModelRecords();
    const counts: Record<ModelGroupKey, number> = {
      library: 0,
      checkpoints: 0,
      exports: 0,
    };

    for (const record of records) {
      counts[record.group] += 1;
    }

    return {
      home: resolveFovuxHome(),
      totalModels: records.length,
      counts,
    };
  }

  getTreeItem(element: ModelTreeNode): vscode.TreeItem {
    return element;
  }

  getChildren(element?: ModelTreeNode): ModelTreeNode[] {
    if (!element) {
      return this.buildGroups();
    }

    if (element instanceof ModelGroupItem) {
      return element.items;
    }

    return [];
  }

  dispose(): void {
    this.disposeWatchers();
    this.onDidChangeEmitter.dispose();
  }

  private buildGroups(): ModelGroupItem[] {
    const records = this.readModelRecords();
    const grouped = new Map<ModelGroupKey, ModelItem[]>();
    for (const key of Object.keys(GROUP_LABELS) as ModelGroupKey[]) {
      grouped.set(key, []);
    }

    for (const record of records) {
      grouped.get(record.group)?.push(new ModelItem(record));
    }

    return (Object.keys(GROUP_LABELS) as ModelGroupKey[])
      .map((key) => new ModelGroupItem(key, grouped.get(key) ?? []))
      .filter((group) => group.items.length > 0);
  }

  private readModelRecords(): ModelRecord[] {
    const home = resolveFovuxHome();
    const roots: Array<{ group: ModelGroupKey; baseDir: string }> = [
      { group: "library", baseDir: path.join(home, "models") },
      { group: "checkpoints", baseDir: path.join(home, "runs") },
      { group: "exports", baseDir: path.join(home, "exports") },
    ];

    const records: ModelRecord[] = [];

    for (const root of roots) {
      if (!fs.existsSync(root.baseDir)) {
        continue;
      }

      for (const filePath of findModelFiles(root.baseDir)) {
        const stat = fs.statSync(filePath);
        const detail = buildDetail(root.baseDir, filePath, root.group);
        records.push({
          label: path.basename(filePath),
          filePath,
          sizeMb: stat.size / 1024 / 1024,
          detail,
          group: root.group,
        });
      }
    }

    return records.sort((left, right) => left.label.localeCompare(right.label));
  }

  private configureWatchers(): void {
    const home = resolveFovuxHome();
    this.watchers = [
      vscode.workspace.createFileSystemWatcher(path.join(home, "models", "**", "*")),
      vscode.workspace.createFileSystemWatcher(path.join(home, "runs", "**", "*")),
      vscode.workspace.createFileSystemWatcher(path.join(home, "exports", "**", "*")),
    ];

    for (const watcher of this.watchers) {
      watcher.onDidChange(() => this.refresh());
      watcher.onDidCreate(() => this.refresh());
      watcher.onDidDelete(() => this.refresh());
    }
  }

  private disposeWatchers(): void {
    for (const watcher of this.watchers) {
      watcher.dispose();
    }
    this.watchers = [];
  }
}

function findModelFiles(root: string): string[] {
  const matches: string[] = [];
  const stack = [root];
  const extensions = new Set([".pt", ".onnx", ".tflite"]);

  while (stack.length > 0) {
    const current = stack.pop();
    if (!current) {
      continue;
    }

    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const nextPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(nextPath);
        continue;
      }

      if (extensions.has(path.extname(entry.name).toLowerCase())) {
        matches.push(nextPath);
      }
    }
  }

  return matches;
}

function buildDetail(baseDir: string, filePath: string, group: ModelGroupKey): string {
  const relativePath = path.relative(baseDir, filePath);
  if (group === "checkpoints") {
    const segments = relativePath.split(path.sep);
    return segments.length > 1 ? segments[0] : "run artifact";
  }
  return relativePath.replace(/\\/g, "/");
}

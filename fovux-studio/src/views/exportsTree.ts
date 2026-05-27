/**
 * Exports TreeView provider.
 *
 * Reads FOVUX_HOME/exports.jsonl and shows recent export/quantization artifacts.
 */

import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

import { resolveFovuxHome } from "../fovux/paths";

interface ExportRecord {
  id: string;
  artifactPath: string;
  sourceCheckpoint: string;
  format: string;
  durationSeconds: number | null;
  createdAt: string | null;
}

export interface ExportsSummary {
  home: string;
  totalExports: number;
}

export class ExportItem extends vscode.TreeItem {
  constructor(private readonly record: ExportRecord) {
    super(path.basename(record.artifactPath), vscode.TreeItemCollapsibleState.None);
    this.tooltip = `${record.artifactPath}\nSource: ${record.sourceCheckpoint}`;
    this.description = buildDescription(record);
    this.iconPath = new vscode.ThemeIcon("archive");
    this.contextValue = "fovuxExport";
    this.command = {
      command: "fovux.revealPath",
      title: "Reveal in Explorer",
      arguments: [record.artifactPath],
    };
  }
}

export class ExportsTreeProvider implements vscode.TreeDataProvider<ExportItem>, vscode.Disposable {
  private readonly onDidChangeEmitter = new vscode.EventEmitter<ExportItem | undefined | null>();
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

  getSummary(): ExportsSummary {
    return {
      home: resolveFovuxHome(),
      totalExports: this.readExports().length,
    };
  }

  getTreeItem(element: ExportItem): vscode.TreeItem {
    return element;
  }

  getChildren(): ExportItem[] {
    return this.readExports().map((record) => new ExportItem(record));
  }

  dispose(): void {
    this.disposeWatchers();
    this.onDidChangeEmitter.dispose();
  }

  private readExports(): ExportRecord[] {
    const historyPath = path.join(resolveFovuxHome(), "exports.jsonl");
    if (!fs.existsSync(historyPath)) {
      return [];
    }

    const records: ExportRecord[] = [];
    for (const line of fs.readFileSync(historyPath, "utf8").split(/\r?\n/)) {
      if (!line.trim()) {
        continue;
      }
      try {
        const raw = JSON.parse(line) as Record<string, unknown>;
        records.push({
          id: String(raw["id"] ?? ""),
          artifactPath: String(raw["artifact_path"] ?? raw["output_path"] ?? ""),
          sourceCheckpoint: String(raw["source_checkpoint"] ?? ""),
          format: String(raw["format"] ?? "artifact"),
          durationSeconds: typeof raw["duration_s"] === "number" ? Number(raw["duration_s"]) : null,
          createdAt: typeof raw["created_at"] === "string" ? raw["created_at"] : null,
        });
      } catch {
        // Ignore partial lines from an in-progress append.
      }
    }

    return records
      .filter((record) => record.artifactPath.length > 0)
      .sort((left, right) => (right.createdAt ?? "").localeCompare(left.createdAt ?? ""));
  }

  private configureWatchers(): void {
    const home = resolveFovuxHome();
    this.watchers = [
      vscode.workspace.createFileSystemWatcher(path.join(home, "exports.jsonl")),
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

function buildDescription(record: ExportRecord): string {
  const parts = [record.format];
  if (record.durationSeconds !== null) {
    parts.push(`${record.durationSeconds.toFixed(1)}s`);
  }
  if (record.createdAt) {
    parts.push(new Date(record.createdAt).toLocaleString());
  }
  return parts.join(" · ");
}

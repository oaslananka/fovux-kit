/**
 * Runs TreeView provider.
 *
 * Reads FOVUX_HOME/runs and displays runs grouped by status.
 */

import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

import { resolveFovuxHome } from "../fovux/paths";

export type RunStatus =
  | "running"
  | "complete"
  | "failed"
  | "stopped"
  | "pending";

type RunTreeNode = RunGroupItem | RunItem;

interface StatusJson {
  status: RunStatus;
  current_epoch?: number;
  total_epochs?: number;
  map50?: number;
  updated_at?: string;
}

interface RunRecord {
  runId: string;
  runPath: string;
  status: RunStatus;
  statusData: StatusJson | null;
  lastUpdatedMs: number | null;
}

export interface RunsSummary {
  home: string;
  totalRuns: number;
  counts: Record<RunStatus, number>;
  activeRuns: number;
  latestMap50: number | null;
}

export interface RunDecorationSummary {
  runPath: string;
  status: RunStatus;
}

const STATUS_ORDER: RunStatus[] = [
  "running",
  "pending",
  "complete",
  "failed",
  "stopped",
];
const STATUS_LABELS: Record<RunStatus, string> = {
  running: "Running",
  pending: "Pending",
  complete: "Completed",
  failed: "Failed",
  stopped: "Stopped",
};

class RunGroupItem extends vscode.TreeItem {
  constructor(
    public readonly status: RunStatus,
    public readonly items: RunItem[],
  ) {
    super(STATUS_LABELS[status], vscode.TreeItemCollapsibleState.Expanded);
    this.description = `${items.length}`;
    this.tooltip = `${STATUS_LABELS[status]} runs`;
    this.iconPath = RunItem.iconForStatus(status);
    this.contextValue = "fovuxRunGroup";
  }
}

export class RunItem extends vscode.TreeItem {
  constructor(private readonly record: RunRecord) {
    super(record.runId, vscode.TreeItemCollapsibleState.None);
    this.tooltip = `${record.runPath}\n${STATUS_LABELS[record.status]}`;
    this.iconPath = RunItem.iconForStatus(record.status);
    this.description = RunItem.descriptionFor(record);
    this.contextValue = RunItem.contextValueFor(record.status);
    this.command = {
      command: "fovux.revealPath",
      title: "Reveal in Explorer",
      arguments: [record.runPath],
    };
  }

  get runId(): string {
    return this.record.runId;
  }

  get runPath(): string {
    return this.record.runPath;
  }

  get status(): RunStatus {
    return this.record.status;
  }

  static iconForStatus(status: RunStatus): vscode.ThemeIcon {
    switch (status) {
      case "running":
        return new vscode.ThemeIcon("sync~spin");
      case "complete":
        return new vscode.ThemeIcon(
          "pass",
          new vscode.ThemeColor("testing.iconPassed"),
        );
      case "failed":
        return new vscode.ThemeIcon(
          "error",
          new vscode.ThemeColor("testing.iconFailed"),
        );
      case "stopped":
        return new vscode.ThemeIcon("debug-stop");
      case "pending":
      default:
        return new vscode.ThemeIcon("circle-outline");
    }
  }

  private static contextValueFor(status: RunStatus): string {
    switch (status) {
      case "running":
        return "fovuxRunRunning";
      case "stopped":
      case "failed":
        return "fovuxRunResumable";
      default:
        return "fovuxRun";
    }
  }

  private static descriptionFor(record: RunRecord): string {
    const parts: string[] = [];
    const data = record.statusData;

    if (data?.current_epoch != null && data.total_epochs != null) {
      parts.push(`${data.current_epoch}/${data.total_epochs}`);
    }
    if (data?.map50 != null) {
      parts.push(`mAP50 ${data.map50.toFixed(3)}`);
    }
    if (record.lastUpdatedMs != null) {
      parts.push(formatRelativeAge(record.lastUpdatedMs));
    }

    return parts.join(" · ");
  }
}

export class RunsTreeProvider
  implements vscode.TreeDataProvider<RunTreeNode>, vscode.Disposable
{
  private readonly onDidChangeEmitter = new vscode.EventEmitter<
    RunTreeNode | undefined | null
  >();
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

  getSummary(): RunsSummary {
    const records = this.readRunRecords();
    const counts: Record<RunStatus, number> = {
      running: 0,
      pending: 0,
      complete: 0,
      failed: 0,
      stopped: 0,
    };

    for (const record of records) {
      counts[record.status] += 1;
    }
    const latestMap50 =
      records
        .map((record) => record.statusData?.map50)
        .find((value): value is number => typeof value === "number") ?? null;

    return {
      home: resolveFovuxHome(),
      totalRuns: records.length,
      counts,
      activeRuns: counts.running,
      latestMap50,
    };
  }

  getRunDecorations(): RunDecorationSummary[] {
    return this.readRunRecords().map((record) => ({
      runPath: record.runPath,
      status: record.status,
    }));
  }

  getTreeItem(element: RunTreeNode): vscode.TreeItem {
    return element;
  }

  getChildren(element?: RunTreeNode): RunTreeNode[] {
    if (!element) {
      return this.buildGroups();
    }

    if (element instanceof RunGroupItem) {
      return element.items;
    }

    return [];
  }

  dispose(): void {
    this.disposeWatchers();
    this.onDidChangeEmitter.dispose();
  }

  private buildGroups(): RunGroupItem[] {
    const records = this.readRunRecords();
    const grouped = new Map<RunStatus, RunItem[]>();
    for (const status of STATUS_ORDER) {
      grouped.set(status, []);
    }

    for (const record of records) {
      grouped.get(record.status)?.push(new RunItem(record));
    }

    return STATUS_ORDER.map(
      (status) => new RunGroupItem(status, grouped.get(status) ?? []),
    ).filter((group) => group.items.length > 0);
  }

  private readRunRecords(): RunRecord[] {
    const runsDir = path.join(resolveFovuxHome(), "runs");
    if (!fs.existsSync(runsDir)) {
      return [];
    }

    const entries = fs.readdirSync(runsDir, { withFileTypes: true });
    const records: RunRecord[] = [];

    for (const entry of entries) {
      if (!entry.isDirectory()) {
        continue;
      }

      const runPath = path.join(runsDir, entry.name);
      const statusFile = path.join(runPath, "status.json");
      let statusData: StatusJson | null = null;
      let status: RunStatus = "pending";
      let lastUpdatedMs: number | null = null;

      if (fs.existsSync(statusFile)) {
        try {
          statusData = JSON.parse(
            fs.readFileSync(statusFile, "utf8"),
          ) as StatusJson;
          status = normalizeStatus(statusData.status ?? "pending");
          lastUpdatedMs = fs.statSync(statusFile).mtimeMs;
        } catch {
          status = "pending";
        }
      }

      records.push({
        runId: entry.name,
        runPath,
        status,
        statusData,
        lastUpdatedMs,
      });
    }

    return records.sort((left, right) => {
      if (left.lastUpdatedMs != null && right.lastUpdatedMs != null) {
        return right.lastUpdatedMs - left.lastUpdatedMs;
      }
      return left.runId.localeCompare(right.runId);
    });
  }

  private configureWatchers(): void {
    const home = resolveFovuxHome();
    this.watchers = [
      vscode.workspace.createFileSystemWatcher(
        path.join(home, "runs", "**", "status.json"),
      ),
      vscode.workspace.createFileSystemWatcher(
        path.join(home, "runs", "**", "metrics.jsonl"),
      ),
      vscode.workspace.createFileSystemWatcher(
        path.join(home, "runs", "**", "results.csv"),
      ),
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

function normalizeStatus(status: string): RunStatus {
  if (status === "completed") {
    return "complete";
  }
  if (
    ["running", "complete", "failed", "stopped", "pending"].includes(status)
  ) {
    return status as RunStatus;
  }
  return "pending";
}

function formatRelativeAge(timestampMs: number): string {
  const diffSeconds = Math.max(
    0,
    Math.round((Date.now() - timestampMs) / 1000),
  );
  if (diffSeconds < 60) {
    return `${diffSeconds}s ago`;
  }
  if (diffSeconds < 3600) {
    return `${Math.floor(diffSeconds / 60)}m ago`;
  }
  if (diffSeconds < 86400) {
    return `${Math.floor(diffSeconds / 3600)}h ago`;
  }
  return `${Math.floor(diffSeconds / 86400)}d ago`;
}

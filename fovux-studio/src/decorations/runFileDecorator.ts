import * as vscode from "vscode";

const STATUS_BADGES: Record<
  string,
  { badge: string; color: vscode.ThemeColor }
> = {
  complete: { badge: "✓", color: new vscode.ThemeColor("charts.green") },
  completed: { badge: "✓", color: new vscode.ThemeColor("charts.green") },
  failed: { badge: "✗", color: new vscode.ThemeColor("charts.red") },
  running: { badge: "▶", color: new vscode.ThemeColor("charts.yellow") },
  stopped: { badge: "■", color: new vscode.ThemeColor("disabledForeground") },
};

export class RunFileDecorationProvider
  implements vscode.FileDecorationProvider, vscode.Disposable
{
  private readonly onDidChangeEmitter = new vscode.EventEmitter<vscode.Uri[]>();
  readonly onDidChangeFileDecorations = this.onDidChangeEmitter.event;
  private readonly cache = new Map<string, string>();

  provideFileDecoration(uri: vscode.Uri): vscode.FileDecoration | undefined {
    const status = this.cache.get(uri.fsPath);
    if (!status) {
      return undefined;
    }
    const badge = STATUS_BADGES[status];
    if (!badge) {
      return undefined;
    }
    return new vscode.FileDecoration(
      badge.badge,
      `Fovux run: ${status}`,
      badge.color,
    );
  }

  update(runs: Array<{ runPath: string; status: string }>): void {
    this.cache.clear();
    const uris: vscode.Uri[] = [];
    for (const run of runs) {
      this.cache.set(run.runPath, run.status);
      uris.push(vscode.Uri.file(run.runPath));
    }
    this.onDidChangeEmitter.fire(uris);
  }

  dispose(): void {
    this.onDidChangeEmitter.dispose();
    this.cache.clear();
  }
}

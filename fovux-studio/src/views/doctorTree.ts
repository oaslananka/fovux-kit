/**
 * Doctor sidebar tree view for system health diagnostics.
 */

import * as vscode from "vscode";
import { ExtensionFovuxClient } from "../fovux/extensionClient";

type DoctorStatus = "pass" | "warn" | "fail";

interface PackageHealth {
  status: "ok" | "missing";
  version?: string | null;
  detail?: string;
}

interface DoctorReport {
  python?: string;
  gpu?: {
    available: boolean;
    accelerator: string;
    device?: string | null;
    detail?: string;
    cuda_version?: string | null;
    memory_free_gb?: number | null;
    memory_total_gb?: number | null;
  };
  ultralytics?: PackageHealth;
  onnxruntime?: PackageHealth;
  onnx?: PackageHealth;
  fastmcp?: PackageHealth;
  http?: { reachable: boolean; detail?: string };
  fovux_home?: {
    path: string;
    writable: boolean;
    disk_free_gb: number;
    disk_low: boolean;
  };
  system?: {
    active_runs?: number;
    cpu_percent?: number;
    ram_percent?: number;
    ram_total_gb?: number;
  };
  requirements?: Record<string, boolean>;
  warnings?: string[];
  errors?: string[];
}

interface DoctorCheck {
  name: string;
  status: DoctorStatus;
  detail: string;
  fixCommand?: string;
}

export class DoctorTreeProvider
  implements vscode.TreeDataProvider<DoctorCheck>, vscode.Disposable
{
  private readonly onDidChangeTreeDataEmitter = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.onDidChangeTreeDataEmitter.event;
  private readonly refreshTimer: NodeJS.Timeout;
  private checks: DoctorCheck[] = [];

  constructor() {
    this.refreshTimer = setInterval(() => void this.refresh(), 60_000);
    this.refreshTimer.unref?.();
  }

  async refresh(): Promise<void> {
    try {
      const client = await ExtensionFovuxClient.create();
      const result = await client.invokeTool<DoctorReport>("fovux_doctor", {});
      this.checks = mapDoctorReport(result);
    } catch {
      this.checks = [
        {
          name: "Server Connection",
          status: "fail",
          detail: "Could not reach fovux-mcp server.",
          fixCommand: "fovux.startServer",
        },
      ];
    }
    this.onDidChangeTreeDataEmitter.fire();
  }

  async fixCheck(element: DoctorCheck | undefined): Promise<void> {
    if (!element?.fixCommand) {
      void vscode.window.showInformationMessage(
        "No automatic fix is available for this check.",
      );
      return;
    }
    await vscode.commands.executeCommand(element.fixCommand);
  }

  getTreeItem(element: DoctorCheck): vscode.TreeItem {
    const icon =
      element.status === "pass"
        ? new vscode.ThemeIcon(
            "check",
            new vscode.ThemeColor("testing.iconPassed"),
          )
        : element.status === "warn"
          ? new vscode.ThemeIcon(
              "warning",
              new vscode.ThemeColor("testing.iconQueued"),
            )
          : new vscode.ThemeIcon(
              "error",
              new vscode.ThemeColor("testing.iconFailed"),
            );

    const item = new vscode.TreeItem(element.name);
    item.description = element.detail;
    item.iconPath = icon;
    item.tooltip = `${element.name}: ${element.status}\n${element.detail}`;
    item.contextValue = element.fixCommand
      ? "fovuxDoctorFixable"
      : "fovuxDoctorCheck";
    if (element.fixCommand) {
      item.command = {
        command: "fovux.fixDoctorCheck",
        title: "Fix",
        arguments: [element],
      };
    }
    return item;
  }

  getChildren(): DoctorCheck[] {
    return this.checks;
  }

  dispose(): void {
    clearInterval(this.refreshTimer);
    this.onDidChangeTreeDataEmitter.dispose();
  }
}

function mapDoctorReport(report: DoctorReport): DoctorCheck[] {
  const checks: DoctorCheck[] = [
    {
      name: "Python",
      status:
        report.requirements?.["python_supported"] === false ? "fail" : "pass",
      detail: report.python ?? "unknown",
    },
    packageCheck("Ultralytics", report.ultralytics, "fovux.installBackend"),
    packageCheck(
      "ONNX Runtime",
      report.onnxruntime,
      "fovux.installBackend",
      "warn",
    ),
    packageCheck("ONNX", report.onnx, "fovux.installBackend", "warn"),
    packageCheck("FastMCP", report.fastmcp, "fovux.installBackend"),
    gpuCheck(report),
    {
      name: "HTTP Transport",
      status: report.http?.reachable ? "pass" : "warn",
      detail: report.http?.detail ?? "HTTP status unknown",
      fixCommand: report.http?.reachable ? undefined : "fovux.startServer",
    },
    {
      name: "FOVUX_HOME",
      status:
        report.fovux_home?.writable === false ||
        report.fovux_home?.disk_low === true
          ? "fail"
          : "pass",
      detail: report.fovux_home
        ? `${report.fovux_home.path} - ${report.fovux_home.disk_free_gb} GB free`
        : "FOVUX_HOME status unknown",
      fixCommand:
        report.fovux_home?.writable === false ||
        report.fovux_home?.disk_low === true
          ? "fovux.openFovuxHome"
          : undefined,
    },
    {
      name: "Active Runs",
      status: "pass",
      detail: `${report.system?.active_runs ?? 0} active`,
    },
  ];

  for (const warning of report.warnings ?? []) {
    checks.push({ name: "Warning", status: "warn", detail: warning });
  }
  for (const error of report.errors ?? []) {
    checks.push({
      name: "Error",
      status: "fail",
      detail: error,
      fixCommand: "fovux.openSecurityDoc",
    });
  }
  return checks;
}

function packageCheck(
  name: string,
  pkg: PackageHealth | undefined,
  fixCommand: string,
  missingStatus: DoctorStatus = "fail",
): DoctorCheck {
  const ok = pkg?.status === "ok";
  return {
    name,
    status: ok ? "pass" : missingStatus,
    detail: ok
      ? `${pkg?.version ?? "unknown"} ${pkg?.detail ?? ""}`.trim()
      : (pkg?.detail ?? "missing"),
    fixCommand: ok ? undefined : fixCommand,
  };
}

function gpuCheck(report: DoctorReport): DoctorCheck {
  const gpu = report.gpu;
  if (!gpu?.available) {
    return {
      name: "GPU",
      status: "warn",
      detail: gpu?.detail ?? "No accelerator detected",
    };
  }
  const memory =
    typeof gpu.memory_free_gb === "number" &&
    typeof gpu.memory_total_gb === "number"
      ? ` (${gpu.memory_free_gb}/${gpu.memory_total_gb} GB free)`
      : "";
  const cuda = gpu.cuda_version ? `CUDA ${gpu.cuda_version} - ` : "";
  return {
    name: "GPU",
    status: "pass",
    detail: `${cuda}${gpu.device ?? gpu.accelerator}${memory}`,
  };
}

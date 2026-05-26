/**
 * Fovux status bar items for compatibility state and privacy badge.
 */

import * as vscode from "vscode";
import type { CompatState } from "../fovux/compat";

let compatItem: vscode.StatusBarItem | null = null;
let privacyItem: vscode.StatusBarItem | null = null;
let activeRunsItem: vscode.StatusBarItem | null = null;
let profileItem: vscode.StatusBarItem | null = null;

/**
 * Create or update the compatibility status bar item.
 */
export function updateCompatStatusBar(state: CompatState): void {
  if (!compatItem) {
    compatItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Left,
      50,
    );
  }

  switch (state) {
    case "connected:recommended":
      compatItem.text = "$(check) Fovux: connected";
      compatItem.tooltip = "fovux-mcp server is running a recommended version.";
      compatItem.backgroundColor = undefined;
      compatItem.command = undefined;
      break;
    case "connected:supported":
      compatItem.text = "$(warning) Fovux: connected (supported)";
      compatItem.tooltip =
        "fovux-mcp server version is supported but below recommended. Consider upgrading.";
      compatItem.backgroundColor = new vscode.ThemeColor(
        "statusBarItem.warningBackground",
      );
      compatItem.command = "fovux.openUpgradeGuide";
      break;
    case "incompatible":
      compatItem.text = "$(error) Fovux: incompatible";
      compatItem.tooltip =
        "fovux-mcp server version is outside the supported range. Tool calls are suspended.";
      compatItem.backgroundColor = new vscode.ThemeColor(
        "statusBarItem.errorBackground",
      );
      compatItem.command = "fovux.openUpgradeGuide";
      break;
  }

  compatItem.show();
}

/**
 * Create and show the privacy badge status bar item.
 * Shows a persistent indicator that Fovux operates in local-only mode.
 */
export function showPrivacyBadge(): void {
  if (!privacyItem) {
    privacyItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Left,
      49,
    );
    privacyItem.text = "$(lock) Fovux: local-only";
    privacyItem.tooltip = [
      "Fovux operates in local-only mode:",
      "• HTTP bound to 127.0.0.1",
      "• Bearer-token authentication",
      "• Rate-limited tool calls",
      "• No telemetry or external network beacons",
      "",
      "Click to view SECURITY.md",
    ].join("\n");
    privacyItem.command = "fovux.openSecurityDoc";
  }
  privacyItem.show();
}

export function updateActiveRunsBadge(
  activeRuns: number,
  latestMap50?: number | null,
): void {
  if (!activeRunsItem) {
    activeRunsItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Left,
      48,
    );
    activeRunsItem.tooltip = "Active Fovux training runs";
    activeRunsItem.command = "fovux.openDashboard";
  }

  if (activeRuns <= 0) {
    activeRunsItem.hide();
    return;
  }

  const metric =
    typeof latestMap50 === "number"
      ? ` | mAP50: ${latestMap50.toFixed(3)}`
      : "";
  activeRunsItem.text = `$(loading~spin) Fovux: ${activeRuns} runs active${metric}`;
  activeRunsItem.show();
}

export function updateProfileStatusBar(profileName: string | null): void {
  if (!profileItem) {
    profileItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Left,
      47,
    );
    profileItem.command = "fovux.selectProfile";
  }

  profileItem.text = `$(account) Fovux: [${profileName || "default"}]`;
  profileItem.tooltip =
    "Select the active FOVUX_HOME profile for this VS Code session.";
  profileItem.show();
}

/**
 * Hide the compatibility status bar item.
 */
export function hideCompatStatusBar(): void {
  compatItem?.hide();
}

/**
 * Dispose all status bar items.
 */
export function disposeStatusBarItems(): void {
  compatItem?.dispose();
  compatItem = null;
  privacyItem?.dispose();
  privacyItem = null;
  activeRunsItem?.dispose();
  activeRunsItem = null;
  profileItem?.dispose();
  profileItem = null;
}

/**
 * Thin wrapper around VS Code output channel for structured logging.
 */

import * as vscode from "vscode";

let _channel: vscode.OutputChannel | undefined;

function getChannel(): vscode.OutputChannel {
  if (!_channel) {
    _channel = vscode.window.createOutputChannel("Fovux Studio");
  }
  return _channel;
}

export const logger = {
  info: (msg: string): void => {
    getChannel().appendLine(`[INFO] ${new Date().toISOString()} ${msg}`);
  },
  warn: (msg: string): void => {
    getChannel().appendLine(`[WARN] ${new Date().toISOString()} ${msg}`);
  },
  error: (msg: string, err?: unknown): void => {
    const detail = err instanceof Error ? ` — ${err.message}` : "";
    getChannel().appendLine(`[ERROR] ${new Date().toISOString()} ${msg}${detail}`);
  },
};

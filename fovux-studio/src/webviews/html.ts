import { randomBytes } from "node:crypto";

import * as vscode from "vscode";

export function createWebviewHtml(
  webview: vscode.Webview,
  extensionUri: vscode.Uri,
  entryPath: string,
  initialState: unknown
): string {
  const bundleUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, "out", ...entryPath.split("/"))
  );
  const nonce = getNonce();
  const serializedState = JSON.stringify(initialState).replace(/</g, "\\u003c");
  const escapedBundleUri = bundleUri.toString().replace(/\\/g, "\\\\").replace(/'/g, "\\'");
  const csp = [
    "default-src 'none'",
    `img-src ${webview.cspSource} data: blob:`,
    `style-src ${webview.cspSource} 'unsafe-inline'`,
    `font-src ${webview.cspSource}`,
    `connect-src http://127.0.0.1:* https://127.0.0.1:*`,
    `script-src ${webview.cspSource} 'nonce-${nonce}'`,
  ].join("; ");

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta http-equiv="Content-Security-Policy" content="${csp}" />
    <title>Fovux Studio</title>
  </head>
  <body style="margin:0;padding:0;background:var(--vscode-editor-background);color:var(--vscode-editor-foreground);">
    <div id="root" style="min-height:100vh;display:grid;place-items:center;padding:24px;box-sizing:border-box;">
      <div style="display:grid;gap:8px;text-align:center;max-width:480px;">
        <strong>Loading Fovux Studio…</strong>
        <span style="color:var(--vscode-descriptionForeground);font-size:12px;">
          If this view stays empty, reload the window and make sure the local HTTP server is running.
        </span>
      </div>
    </div>
    <script nonce="${nonce}">
      window.__FOVUX_INITIAL_STATE__ = ${serializedState};

      (function () {
        const root = document.getElementById("root");

        const showError = (title, detail) => {
          if (!root) {
            return;
          }
          root.innerHTML = "";

          const panel = document.createElement("div");
          panel.style.display = "grid";
          panel.style.gap = "10px";
          panel.style.maxWidth = "640px";
          panel.style.padding = "24px";
          panel.style.borderRadius = "16px";
          panel.style.background = "var(--vscode-inputValidation-errorBackground)";
          panel.style.border = "1px solid var(--vscode-inputValidation-errorBorder)";
          panel.style.color = "var(--vscode-editor-foreground)";

          const heading = document.createElement("strong");
          heading.textContent = title;
          panel.appendChild(heading);

          const body = document.createElement("span");
          body.style.fontSize = "12px";
          body.style.lineHeight = "1.5";
          body.textContent = detail;
          panel.appendChild(body);

          root.appendChild(panel);
        };

        window.addEventListener("error", (event) => {
          const message = event.error?.message || event.message || "Unknown webview error.";
          showError("Fovux Studio failed to render.", message);
        });

        window.addEventListener("unhandledrejection", (event) => {
          const reason = event.reason;
          const message =
            typeof reason === "string"
              ? reason
              : reason?.message || "Unhandled promise rejection while booting the webview.";
          showError("Fovux Studio failed to initialize.", message);
        });

        const script = document.createElement("script");
        script.src = '${escapedBundleUri}';
        script.nonce = "${nonce}";
        script.addEventListener("error", () => {
          showError(
            "Fovux Studio bundle could not be loaded.",
            "The packaged webview script did not load. Reinstall the latest VSIX and reload the VS Code window."
          );
        });
        document.body.appendChild(script);
      })();
    </script>
  </body>
</html>`;
}

export function getNonce(): string {
  return randomBytes(16).toString("base64url");
}

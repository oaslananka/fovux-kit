import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import "./helpers/vscodeMock";
import {
  ExtensionFovuxClient,
  getAuthToken,
  getFovuxBaseUrl,
} from "../../src/fovux/extensionClient";
import { createWebviewHtml, getNonce } from "../../src/webviews/html";

describe("Fovux client and webview host", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env["FOVUX_HOME"];
  });

  it("builds the configured localhost base URL", () => {
    expect(getFovuxBaseUrl()).toBe("http://127.0.0.1:7823");
  });

  it("invokes tools over the HTTP bridge", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ total: 1 }),
    }));
    vi.stubGlobal("fetch", fetchMock);
    const home = fs.mkdtempSync(path.join(os.tmpdir(), "fovux-client-"));
    process.env["FOVUX_HOME"] = home;
    fs.writeFileSync(path.join(home, "auth.token"), "secret-token\n");

    const client = await ExtensionFovuxClient.create();
    const response = await client.invokeTool<{ total: number }>("model_list", {});

    expect(response.total).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:7823/tools/model_list",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer secret-token" }),
      })
    );
  });

  it("rereads auth.token and retries once after a 401", async () => {
    const home = fs.mkdtempSync(path.join(os.tmpdir(), "fovux-token-rotation-"));
    process.env["FOVUX_HOME"] = home;
    fs.writeFileSync(path.join(home, "auth.token"), "old-token\n");
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const headers = init?.headers as Record<string, string> | undefined;
      if (fetchMock.mock.calls.length === 1) {
        fs.writeFileSync(path.join(home, "auth.token"), "new-token\n");
        expect(headers?.["Authorization"]).toBe("Bearer old-token");
        return { ok: false, status: 401, statusText: "Unauthorized", json: async () => ({}) };
      }
      expect(headers?.["Authorization"]).toBe("Bearer new-token");
      return { ok: true, status: 200, statusText: "OK", json: async () => [] };
    });
    vi.stubGlobal("fetch", fetchMock);

    const client = await ExtensionFovuxClient.create();
    await expect(client.listRuns()).resolves.toEqual([]);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(client.getAuthToken()).toBe("new-token");
  });

  it("reads the persisted auth token from FOVUX_HOME", async () => {
    const home = fs.mkdtempSync(path.join(os.tmpdir(), "fovux-auth-"));
    process.env["FOVUX_HOME"] = home;
    fs.writeFileSync(path.join(home, "auth.token"), "token-from-disk\n");

    await expect(getAuthToken()).resolves.toBe("token-from-disk");
  });

  it("renders HTML that boots the requested webview bundle", () => {
    const html = createWebviewHtml(
      {
        cspSource: "vscode-webview-resource",
        asWebviewUri: (uri: { path?: string; fsPath?: string }) => ({
          toString: () => `vscode-resource:${uri.path ?? uri.fsPath ?? ""}`,
        }),
      } as never,
      { path: "/extension" } as never,
      "webviews/exportWizard/main.js",
      { hello: "fovux" }
    );

    expect(html).toContain("webviews/exportWizard/main.js");
    expect(html).toContain("window.__FOVUX_INITIAL_STATE__");
    expect(html).toContain("connect-src http://127.0.0.1:* https://127.0.0.1:*");
    const cspNonce = html.match(/script-src[^"]*'nonce-([A-Za-z0-9_-]+)'/);
    const scriptNonce = html.match(/<script nonce="([A-Za-z0-9_-]+)">/);
    expect(cspNonce?.[1]).toBeTruthy();
    expect(scriptNonce?.[1]).toBe(cspNonce?.[1]);
  });

  it("generates cryptographic base64url CSP nonces", () => {
    const first = getNonce();
    const second = getNonce();

    expect(first).toMatch(/^[A-Za-z0-9_-]{22}$/);
    expect(second).toMatch(/^[A-Za-z0-9_-]{22}$/);
    expect(first).not.toBe(second);
  });
});

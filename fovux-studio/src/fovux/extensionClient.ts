import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as vscode from "vscode";

import { resolveFovuxHome } from "./paths";

export interface RunSummary {
  id: string;
  status: string;
  model: string;
  epochs: number;
  run_path?: string;
  current_epoch?: number | null;
  best_map50?: number | null;
  created_at: string | null;
}

export interface RunDetail extends RunSummary {
  dataset_path?: string;
  task?: string;
  pid?: number | null;
  run_path?: string;
  current_epoch?: number | null;
  best_map50?: number | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export class ExtensionFovuxClient {
  private readonly baseUrl: string;
  private authToken: string | null;

  private constructor(baseUrl: string, authToken: string | null) {
    this.baseUrl = baseUrl;
    this.authToken = authToken;
  }

  static async create(): Promise<ExtensionFovuxClient> {
    return new ExtensionFovuxClient(getFovuxBaseUrl(), await getAuthToken());
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  getAuthToken(): string | null {
    return this.authToken;
  }

  async listRuns(): Promise<RunSummary[]> {
    return this.requestJson<RunSummary[]>("/runs", {}, "fovux-mcp HTTP error");
  }

  async getRun(runId: string): Promise<RunDetail> {
    return this.requestJson<RunDetail>(`/runs/${encodeURIComponent(runId)}`, {}, `Run ${runId}`);
  }

  async health(): Promise<boolean> {
    try {
      const res = await fetch(`${this.baseUrl}/health`);
      return res.ok;
    } catch {
      return false;
    }
  }

  async invokeTool<T>(name: string, payload: Record<string, unknown>): Promise<T> {
    return this.requestJson<T>(
      `/tools/${encodeURIComponent(name)}`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      `Tool ${name} failed`
    );
  }

  async refreshAuthToken(): Promise<string | null> {
    this.authToken = await getAuthToken();
    return this.authToken;
  }

  private async requestJson<T>(
    pathName: string,
    init: RequestInit,
    errorPrefix: string
  ): Promise<T> {
    const res = await this.fetchWithAuth(`${this.baseUrl}${pathName}`, init);

    if (!res.ok) {
      const detail = await safeJson(res);
      throw new Error(`${errorPrefix}: ${extractErrorMessage(detail, res)}`);
    }
    return res.json() as Promise<T>;
  }

  private async fetchWithAuth(url: string, init: RequestInit): Promise<Response> {
    const first = await fetch(url, {
      ...init,
      headers: buildHeaders(this.authToken, init.headers),
    });

    if (first.status !== 401) {
      return first;
    }

    this.authToken = await getAuthToken();
    return fetch(url, {
      ...init,
      headers: buildHeaders(this.authToken, init.headers),
    });
  }
}

export function getFovuxBaseUrl(): string {
  const config = vscode.workspace.getConfiguration("fovux");
  const port = config.get<number>("httpPort") ?? 7823;
  return `http://127.0.0.1:${port}`;
}

export async function getAuthToken(): Promise<string | null> {
  const tokenPath = path.join(resolveFovuxHome(), "auth.token");
  try {
    return (await fs.readFile(tokenPath, "utf-8")).trim();
  } catch {
    return null;
  }
}

function buildHeaders(authToken: string | null, extra?: HeadersInit): Record<string, string> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (extra instanceof Headers) {
    extra.forEach((value, key) => {
      headers[key] = value;
    });
  } else if (Array.isArray(extra)) {
    for (const [key, value] of extra) {
      headers[key] = value;
    }
  } else if (extra) {
    Object.assign(headers, extra);
  }
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  return headers;
}

async function safeJson(response: Response): Promise<unknown> {
  try {
    return (await response.json()) as unknown;
  } catch {
    return { status: response.status, statusText: response.statusText };
  }
}

function extractErrorMessage(detail: unknown, response: Response): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    const nested = record["detail"];
    if (typeof nested === "string") {
      return nested;
    }
    if (nested && typeof nested === "object") {
      const nestedRecord = nested as Record<string, unknown>;
      const code = typeof nestedRecord["code"] === "string" ? `${nestedRecord["code"]}: ` : "";
      if (typeof nestedRecord["message"] === "string") {
        return `${code}${nestedRecord["message"]}`;
      }
    }
    if (typeof record["message"] === "string") {
      return record["message"];
    }
  }
  return `HTTP ${response.status} ${response.statusText}`;
}

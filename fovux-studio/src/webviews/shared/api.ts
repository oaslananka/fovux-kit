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

export interface MetricPayload {
  runId: string;
  epoch: number;
  metrics: Record<string, number>;
}

export interface HttpClientConfig {
  baseUrl: string;
  authToken: string | null;
}

const POLL_FALLBACK_INTERVAL_MS = 2000;

class StreamUnavailableError extends Error {}

export async function listRuns(
  config: HttpClientConfig,
): Promise<RunSummary[]> {
  const response = await fetch(`${config.baseUrl}/runs`, {
    headers: authHeaders(config.authToken),
  });
  return handleResponse<RunSummary[]>(response);
}

export async function getRun(
  config: HttpClientConfig,
  runId: string,
): Promise<RunDetail> {
  const response = await fetch(`${config.baseUrl}/runs/${runId}`, {
    headers: authHeaders(config.authToken),
  });
  return handleResponse<RunDetail>(response);
}

export async function invokeTool<T>(
  config: HttpClientConfig,
  name: string,
  payload: Record<string, unknown>,
): Promise<T> {
  const response = await fetch(`${config.baseUrl}/tools/${name}`, {
    method: "POST",
    headers: authHeaders(config.authToken),
    body: JSON.stringify(payload),
  });
  return handleResponse<T>(response);
}

export function subscribeToMetrics(
  config: HttpClientConfig,
  runId: string,
  onMetric: (payload: MetricPayload) => void,
  onError?: (error: string) => void,
  onDone?: () => void,
): () => void {
  const controller = new AbortController();

  void streamEvents(
    config,
    runId,
    controller.signal,
    onMetric,
    onError,
    onDone,
  );

  return () => {
    controller.abort();
  };
}

async function streamEvents(
  config: HttpClientConfig,
  runId: string,
  signal: AbortSignal,
  onMetric: (payload: MetricPayload) => void,
  onError?: (error: string) => void,
  onDone?: () => void,
): Promise<void> {
  let attempt = 0;
  while (!signal.aborted) {
    try {
      const completed = await connectAndStream(config, runId, signal, onMetric);
      if (completed) {
        onDone?.();
        break;
      }
      if (!signal.aborted) {
        throw new Error(`Metric stream for ${runId} closed.`);
      }
    } catch (error) {
      if (signal.aborted) {
        break;
      }
      if (error instanceof StreamUnavailableError) {
        onError?.(
          `Metric stream unavailable for ${runId}; falling back to polling.`,
        );
        await pollRunMetrics(config, runId, signal, onMetric, onError, onDone);
        break;
      }
      const delayMs = Math.min(1000 * 2 ** attempt, 30_000);
      attempt += 1;
      onError?.(
        `Reconnecting in ${delayMs}ms (attempt ${attempt}): ${
          error instanceof Error ? error.message : String(error)
        }`,
      );
      await sleep(delayMs, signal);
    }
    attempt = 0;
  }
}

async function connectAndStream(
  config: HttpClientConfig,
  runId: string,
  signal: AbortSignal,
  onMetric: (payload: MetricPayload) => void,
): Promise<boolean> {
  let response = await fetch(
    `${config.baseUrl}/runs/${encodeURIComponent(runId)}/stream`,
    {
      headers: authHeaders(config.authToken),
      signal,
    },
  );
  if (response.status === 404) {
    response = await fetch(
      `${config.baseUrl}/runs/${encodeURIComponent(runId)}/metrics`,
      {
        headers: authHeaders(config.authToken),
        signal,
      },
    );
  }
  if (!response.ok || response.body === null) {
    if (
      response.status === 404 ||
      response.status === 405 ||
      response.status === 501
    ) {
      throw new StreamUnavailableError(
        `Metric stream is unavailable for ${runId}.`,
      );
    }
    throw new Error(
      `Metric stream failed for ${runId} (HTTP ${response.status}).`,
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (!signal.aborted) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const eventChunk of events) {
      if (isDoneEvent(eventChunk)) {
        return true;
      }
      const payload = parseMetricEvent(eventChunk);
      if (payload !== null) {
        onMetric(payload);
      }
    }
  }
  return false;
}

export function parseMetricEvent(chunk: string): MetricPayload | null {
  let eventName = "";
  const dataLines: string[] = [];
  for (const line of chunk.split("\n")) {
    if (line.startsWith(":") || line.trim() === "") {
      continue;
    }
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }
  if (!["metric", "metrics"].includes(eventName) || dataLines.length === 0) {
    return null;
  }
  return JSON.parse(dataLines.join("\n")) as MetricPayload;
}

async function pollRunMetrics(
  config: HttpClientConfig,
  runId: string,
  signal: AbortSignal,
  onMetric: (payload: MetricPayload) => void,
  onError?: (error: string) => void,
  onDone?: () => void,
): Promise<void> {
  let lastEpoch: number | null = null;
  while (!signal.aborted) {
    try {
      const response = await fetch(
        `${config.baseUrl}/runs/${encodeURIComponent(runId)}`,
        {
          headers: authHeaders(config.authToken),
          signal,
        },
      );
      const run = await handleResponse<RunDetail>(response);
      const epoch =
        typeof run.current_epoch === "number" ? run.current_epoch : 0;
      if (epoch !== lastEpoch && typeof run.best_map50 === "number") {
        onMetric({
          runId,
          epoch,
          metrics: {
            map50: run.best_map50,
            "metrics/mAP50(B)": run.best_map50,
          },
        });
        lastEpoch = epoch;
      }
      if (["complete", "completed", "failed", "stopped"].includes(run.status)) {
        onDone?.();
        break;
      }
    } catch (error) {
      if (!signal.aborted) {
        onError?.(error instanceof Error ? error.message : String(error));
      }
    }
    await sleep(POLL_FALLBACK_INTERVAL_MS, signal);
  }
}

function isDoneEvent(chunk: string): boolean {
  return chunk
    .split("\n")
    .some(
      (line) =>
        line.startsWith("event:") &&
        line.slice("event:".length).trim() === "done",
    );
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
  });
}

function authHeaders(authToken: string | null): HeadersInit {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  return headers;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await safeJson(response);
    throw new Error(extractErrorMessage(detail, response));
  }
  return response.json() as Promise<T>;
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
      const code =
        typeof nestedRecord["code"] === "string"
          ? `${nestedRecord["code"]}: `
          : "";
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

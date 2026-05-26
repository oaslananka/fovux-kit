import { describe, expect, it, vi } from "vitest";

import {
  parseMetricEvent,
  subscribeToMetrics,
  type HttpClientConfig,
} from "../../src/webviews/shared/api";

function streamFrom(chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(new TextEncoder().encode(chunk));
      }
      controller.close();
    },
  });
}

describe("shared webview api", () => {
  const config: HttpClientConfig = {
    baseUrl: "http://127.0.0.1:7823",
    authToken: "token",
  };

  it("parses multiline SSE data fields", () => {
    const payload = parseMetricEvent(
      'event: metric\ndata: {"runId":"run1",\ndata: "epoch":2,"metrics":{"mAP":0.7}}\n',
    );

    expect(payload).toEqual({ runId: "run1", epoch: 2, metrics: { mAP: 0.7 } });
  });

  it("accepts plural metrics SSE events from compatible servers", () => {
    const payload = parseMetricEvent(
      'event: metrics\ndata: {"runId":"run1","epoch":2,"metrics":{"map50":0.7}}\n',
    );

    expect(payload).toEqual({
      runId: "run1",
      epoch: 2,
      metrics: { map50: 0.7 },
    });
  });

  it("reconnects when an SSE stream closes before unsubscribe", async () => {
    vi.useFakeTimers();
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        calls += 1;
        if (calls === 1) {
          return { ok: true, body: streamFrom([]) };
        }
        return {
          ok: true,
          body: streamFrom([
            'event: metric\ndata: {"runId":"run1","epoch":3,"metrics":{"mAP":0.8}}\n\n',
          ]),
        };
      }),
    );

    const received: unknown[] = [];
    const errors: string[] = [];
    const unsubscribe = subscribeToMetrics(
      config,
      "run1",
      (payload) => received.push(payload),
      (error) => errors.push(error),
    );

    await vi.advanceTimersByTimeAsync(1_100);
    await Promise.resolve();
    unsubscribe();

    expect(calls).toBeGreaterThanOrEqual(2);
    expect(received).toContainEqual({
      runId: "run1",
      epoch: 3,
      metrics: { mAP: 0.8 },
    });
    expect(errors.some((error) => error.includes("Reconnecting"))).toBe(true);
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("falls back to polling when both SSE endpoints are unavailable", async () => {
    const received: unknown[] = [];
    const errors: string[] = [];
    const done = vi.fn();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 501, body: null })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "run1",
          status: "completed",
          model: "yolov8n.pt",
          epochs: 5,
          current_epoch: 4,
          best_map50: 0.91,
          created_at: null,
        }),
      });
    vi.stubGlobal("fetch", fetchMock);

    const unsubscribe = subscribeToMetrics(
      config,
      "run1",
      (payload) => received.push(payload),
      (error) => errors.push(error),
      done,
    );

    await vi.waitFor(() => {
      expect(done).toHaveBeenCalledOnce();
    });
    unsubscribe();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(errors[0]).toContain("falling back to polling");
    expect(received).toEqual([
      {
        runId: "run1",
        epoch: 4,
        metrics: { map50: 0.91, "metrics/mAP50(B)": 0.91 },
      },
    ]);
    vi.unstubAllGlobals();
  });
});

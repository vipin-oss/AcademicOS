import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { streamAi } from "./ai";

/**
 * Pins the shared SSE streaming transport (M26): token deltas dispatch to
 * onToken, the completion event dispatches the full result, HTTP errors
 * surface as ApiError with the backend detail, and aborts stay silent.
 */
describe("streamAi", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function mockStream(frames: Array<{ event: string; data: string }>, status = 200) {
    const body = frames
      .map((f) => `event: ${f.event}\ndata: ${f.data}\n\n`)
      .join("");
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(body, { status, headers: { "Content-Type": "text/event-stream" } }),
    );
  }

  it("POSTs to the endpoint with a JSON body and dispatches token deltas", async () => {
    mockStream([
      { event: "token", data: JSON.stringify({ delta: "Hel" }) },
      { event: "token", data: JSON.stringify({ delta: "lo" }) },
      { event: "completion", data: JSON.stringify({ answer: "Hello", available: true }) },
    ]);

    const tokens: string[] = [];
    const completions: Array<Record<string, unknown>> = [];
    await streamAi("/ai/chat/stream", { message: "hi", history: [] }, {
      onToken: (d) => tokens.push(d),
      onCompletion: (d) => completions.push(d),
    });

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain("/ai/chat/stream");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({ message: "hi", history: [] });
    expect(tokens).toEqual(["Hel", "lo"]);
    expect(completions).toEqual([{ answer: "Hello", available: true }]);
  });

  it("throws ApiError with the backend detail on a 404 (feature flag off)", async () => {
    mockStream([], 404);
    await expect(
      streamAi("/ai/assistants/research/stream", { message: "x" }, {}),
    ).rejects.toMatchObject({ status: 404, kind: "http" });
  });

  it("throws ApiError on a 422 with a pydantic detail message", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ detail: [{ loc: ["body", "message"], msg: "field required" }] }),
        { status: 422 },
      ),
    );
    await expect(streamAi("/ai/chat/stream", {}, {})).rejects.toMatchObject({
      status: 422,
    });
  });
});

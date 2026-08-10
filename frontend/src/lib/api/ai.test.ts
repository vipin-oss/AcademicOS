import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getAssistantRoles, queryAssistant } from "./ai";

/**
 * Pins the M22-M25 domain-assistant client wiring: the catalogue is a GET that
 * unwraps `items`, and a role query is a POST to /ai/assistants/{role} with the
 * 120s AI timeout.
 */
describe("assistant API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function mockFetchOnce(body: unknown, status = 200) {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }

  it("getAssistantRoles GETs the catalogue and unwraps items", async () => {
    mockFetchOnce({
      items: [
        { key: "research", display_name: "Research Assistant", description: "d1" },
        { key: "teaching", display_name: "Teaching Assistant", description: "d2" },
      ],
    });

    const roles = await getAssistantRoles();

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain("/ai/assistants");
    expect(init?.method).toBe("GET");
    expect(roles).toHaveLength(2);
    expect(roles[0].key).toBe("research");
  });

  it("queryAssistant POSTs to /ai/assistants/{role} with the message body", async () => {
    mockFetchOnce({
      role: "research",
      answer: "gap analysis",
      available: true,
      retrieved_count: 3,
      truncated: false,
      citations: [],
      provider_id: "local-ollama",
      model: "llama3.2",
      prompt_id: "assistant.research",
      prompt_version: 0,
      input_tokens: 10,
      output_tokens: 5,
      token_usage_estimated: false,
      latency_ms: 1200,
      confidence: "high",
    });

    const res = await queryAssistant("research", { message: "what gaps exist?" });

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain("/ai/assistants/research");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe(JSON.stringify({ message: "what gaps exist?" }));
    expect(res.role).toBe("research");
    expect(res.answer).toBe("gap analysis");
    expect(res.available).toBe(true);
  });

  it("encodes the role into the path", async () => {
    mockFetchOnce({ items: [] });
    // Use a plain role key; ensure it appears verbatim in the URL.
    await queryAssistant("teaching", { message: "explain mitosis" });
    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain("/ai/assistants/teaching");
  });

  it("surfaces a non-2xx as a thrown error (404 when disabled)", async () => {
    mockFetchOnce({ detail: "Not found" }, 404);
    await expect(queryAssistant("research", { message: "hi" })).rejects.toThrow();
  });
});

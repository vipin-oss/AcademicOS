import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { searchObjects, syncSearchIndex } from "./search";

/**
 * Pins the Sprint-5 M2 search client: query params are sent exactly as the
 * backend expects (text/object_type/title/limit) and the sync endpoint is
 * a POST with no body.
 */
describe("search API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function mockFetchOnce(body: unknown, status = 200) {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
    );
  }

  it("sends text/object_type/title/limit as query params", async () => {
    mockFetchOnce({ results: [] });

    await searchObjects({ text: "quantum", object_type: "document", title: "x", limit: 25 });

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain("/search?");
    expect(String(url)).toContain("text=quantum");
    expect(String(url)).toContain("object_type=document");
    expect(String(url)).toContain("title=x");
    expect(String(url)).toContain("limit=25");
    expect(init?.method).toBe("GET");
  });

  it("omits empty params", async () => {
    mockFetchOnce({ results: [] });

    await searchObjects({ text: "physics" });

    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain("text=physics");
    expect(String(url)).not.toContain("object_type=");
    expect(String(url)).not.toContain("title=");
    expect(String(url)).not.toContain("limit=");
  });

  it("returns typed hits with provenance", async () => {
    mockFetchOnce({
      results: [
        {
          object_id: "obj:document:A",
          object_type: "document",
          title: "Quantum Notes",
          version: 2,
          index_source: "both",
          score: 0.032787,
        },
      ],
    });

    const response = await searchObjects({ text: "quantum" });
    expect(response.results[0]).toMatchObject({
      object_id: "obj:document:A",
      index_source: "both",
      score: 0.032787,
    });
  });

  it("syncs the index via POST /search/index/sync", async () => {
    mockFetchOnce({ applied: 7 });

    const response = await syncSearchIndex();
    expect(response).toEqual({ applied: 7 });

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain("/search/index/sync");
    expect(init?.method).toBe("POST");
  });
});

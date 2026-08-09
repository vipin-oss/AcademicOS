import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "./client";

/**
 * Pins the Sprint-3 M3 auth-scoped client behaviour: the bearer token is
 * attached to every request when one is stored, never sent otherwise, and
 * getBlob returns the raw bytes with the same status normalisation.
 */
const TOKEN_KEY = "academicos.access_token";

describe("api client auth wiring", () => {
  beforeEach(() => {
    localStorage.clear();
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

  it("attaches the bearer token when one is stored", async () => {
    localStorage.setItem(TOKEN_KEY, "token-abc");
    mockFetchOnce({ ok: true });

    await api.get("/objects");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer token-abc");
  });

  it("sends no Authorization header without a token", async () => {
    mockFetchOnce({ ok: true });

    await api.get("/health");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("getBlob returns raw bytes", async () => {
    localStorage.setItem(TOKEN_KEY, "token-abc");
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response("%PDF-1.7", { status: 200, headers: { "Content-Type": "application/pdf" } }),
    );

    const blob = await api.getBlob("/documents/obj:document:X/download");

    // jsdom does not implement Blob.text(); use arrayBuffer + TextDecoder.
    const buffer = await blob.arrayBuffer();
    expect(new TextDecoder().decode(buffer)).toBe("%PDF-1.7");
    expect(blob.type).toBe("application/pdf");
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer token-abc");
  });

  it("getBlob normalises HTTP errors to ApiError with the status", async () => {
    mockFetchOnce({ detail: "Invalid or expired token" }, 401);

    await expect(api.getBlob("/documents/obj:document:X/download")).rejects.toMatchObject({
      kind: "http",
      status: 401,
    });
  });
});

/**
 * Upload auth tests (P0 fix): the raw XMLHttpRequest in uploadDocument()
 * must attach the SAME bearer token the shared API client sends
 * (getAccessToken — the single source of truth), without breaking
 * multipart FormData, browser-generated Content-Type, progress,
 * cancellation, or error handling.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { uploadDocument, type CreateDocumentPayload } from "./documents";

const TOKEN_KEY = "academicos.access_token";

class RecordingXHR {
  headers: Record<string, string> = {};
  url = "";
  method = "";
  sentBody: unknown = null;
  status = 201;
  responseText = JSON.stringify({ id: "obj:document:TEST", title: "doc" });
  upload: {
    onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null;
  } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  aborted = false;

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }
  setRequestHeader(key: string, value: string) {
    this.headers[key] = value;
  }
  send(body: unknown) {
    this.sentBody = body;
  }
  abort() {
    this.aborted = true;
    this.onabort?.();
  }
}

function payload(overrides: Partial<CreateDocumentPayload> = {}): CreateDocumentPayload {
  return {
    title: "Test Doc",
    document_type: "pdf",
    uploaded_by: "user:1",
    file: new File(["pdf-bytes"], "test.pdf", { type: "application/pdf" }),
    ...overrides,
  };
}

function lastXHR(): RecordingXHR {
  const calls = vi.mocked(XMLHttpRequest).mock.results;
  return calls[calls.length - 1].value as RecordingXHR;
}

describe("uploadDocument auth (P0 fix)", () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("attaches Authorization: Bearer <token> when a token exists", async () => {
    localStorage.setItem(TOKEN_KEY, "token-abc");
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => new RecordingXHR()));

    const promise = uploadDocument(payload());
    const xhr = lastXHR();
    xhr.onload?.();
    await promise;

    expect(xhr.headers.Authorization).toBe("Bearer token-abc");
  });

  it("sends the exact Bearer format (no prefix/suffix drift)", async () => {
    localStorage.setItem(TOKEN_KEY, "tok.123.xyz");
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => new RecordingXHR()));

    const promise = uploadDocument(payload());
    const xhr = lastXHR();
    xhr.onload?.();
    await promise;

    expect(xhr.headers.Authorization).toMatch(/^Bearer tok\.123\.xyz$/);
  });

  it("sends no Authorization header when no token is stored", async () => {
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => new RecordingXHR()));

    const promise = uploadDocument(payload());
    const xhr = lastXHR();
    xhr.onload?.();
    await promise;

    expect(xhr.headers.Authorization).toBeUndefined();
    expect(Object.keys(xhr.headers)).toHaveLength(0);
  });

  it("keeps FormData as the body (multipart preserved)", async () => {
    localStorage.setItem(TOKEN_KEY, "token-abc");
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => new RecordingXHR()));

    const promise = uploadDocument(payload());
    const xhr = lastXHR();
    xhr.onload?.();
    await promise;

    expect(xhr.sentBody).toBeInstanceOf(FormData);
  });

  it("does NOT manually set Content-Type (browser sets the multipart boundary)", async () => {
    localStorage.setItem(TOKEN_KEY, "token-abc");
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => new RecordingXHR()));

    const promise = uploadDocument(payload());
    const xhr = lastXHR();
    xhr.onload?.();
    await promise;

    expect(xhr.headers["Content-Type"]).toBeUndefined();
  });

  it("still reports upload progress", async () => {
    localStorage.setItem(TOKEN_KEY, "token-abc");
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => new RecordingXHR()));
    const onProgress = vi.fn();

    const promise = uploadDocument(payload(), { onProgress });
    const xhr = lastXHR();
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 });
    xhr.onload?.();
    await promise;

    expect(onProgress).toHaveBeenCalledWith({ percent: 50 });
  });

  it("rejects with ApiError kind=aborted when cancelled before send", async () => {
    localStorage.setItem(TOKEN_KEY, "token-abc");
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => new RecordingXHR()));
    const controller = new AbortController();
    controller.abort();

    await expect(uploadDocument(payload(), { signal: controller.signal })).rejects.toMatchObject({
      kind: "aborted",
    });
  });

  it("rejects with ApiError kind=aborted when aborted mid-flight", async () => {
    localStorage.setItem(TOKEN_KEY, "token-abc");
    const xhr = new RecordingXHR();
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => xhr));
    const controller = new AbortController();

    const promise = uploadDocument(payload(), { signal: controller.signal });
    controller.abort();
    await expect(promise).rejects.toMatchObject({ kind: "aborted" });
    expect(xhr.aborted).toBe(true);
  });

  it("still parses success responses into DocumentResponse", async () => {
    localStorage.setItem(TOKEN_KEY, "token-abc");
    const xhr = new RecordingXHR();
    xhr.responseText = JSON.stringify({ id: "obj:document:OK", title: "saved" });
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => xhr));

    const promise = uploadDocument(payload());
    xhr.onload?.();
    const result = await promise;

    expect(result.id).toBe("obj:document:OK");
  });

  it("still normalises HTTP errors (401 -> ApiError with status + detail)", async () => {
    localStorage.setItem(TOKEN_KEY, "token-abc");
    const xhr = new RecordingXHR();
    xhr.status = 401;
    xhr.responseText = JSON.stringify({ detail: "Invalid or expired token" });
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => xhr));

    const promise = uploadDocument(payload());
    xhr.onload?.();

    await expect(promise).rejects.toMatchObject({
      kind: "http",
      status: 401,
      message: "Invalid or expired token",
    });
  });

  it("keeps the endpoint and method unchanged", async () => {
    localStorage.setItem(TOKEN_KEY, "token-abc");
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => new RecordingXHR()));

    const promise = uploadDocument(payload());
    const xhr = lastXHR();
    xhr.onload?.();
    await promise;

    expect(xhr.method).toBe("POST");
    expect(xhr.url.endsWith("/documents")).toBe(true);
  });
});

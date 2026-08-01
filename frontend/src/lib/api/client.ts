import { API_BASE_URL } from "@/config/env";

/**
 * Thin fetch wrapper. No business logic — transport + error normalisation only.
 *
 * Guarantees relied on by the whole app:
 *  - every failure is an {@link ApiError} carrying the HTTP status and the
 *    *backend* message (FastAPI `detail`) whenever the server sent one;
 *  - network / offline / timeout / cancellation are distinguishable;
 *  - `Content-Type: application/json` is only sent when there IS a body, so
 *    plain GET/DELETE stay CORS-simple and skip the preflight round-trip;
 *  - 204 (and empty bodies) resolve to `undefined` instead of throwing.
 */

export const DEFAULT_TIMEOUT_MS = 15_000;

export type ApiErrorKind = "http" | "network" | "offline" | "timeout" | "aborted";

const STATUS_FALLBACK: Record<number, string> = {
  400: "The request was invalid.",
  401: "Your session has expired. Please sign in again.",
  403: "You do not have permission to perform this action.",
  404: "The requested resource was not found.",
  409: "This conflicts with the current state of the resource.",
  422: "Some of the submitted values are invalid.",
  429: "Too many requests. Please slow down and try again.",
  500: "The server encountered an unexpected error.",
  502: "The server is temporarily unavailable.",
  503: "The server is temporarily unavailable.",
  504: "The server took too long to respond.",
};

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly details: unknown;

  constructor(
    message: string,
    options: { kind: ApiErrorKind; status?: number | null; details?: unknown },
  ) {
    super(message);
    this.name = "ApiError";
    this.kind = options.kind;
    this.status = options.status ?? null;
    this.details = options.details;
    // Required so `instanceof` survives the ES5 downlevel target.
    Object.setPrototypeOf(this, ApiError.prototype);
  }

  get isAborted(): boolean {
    return this.kind === "aborted";
  }
  get isOffline(): boolean {
    return this.kind === "offline";
  }
  get isTimeout(): boolean {
    return this.kind === "timeout";
  }
  get isNetwork(): boolean {
    return this.kind === "network";
  }
  get isNotFound(): boolean {
    return this.status === 404;
  }
  get isConflict(): boolean {
    return this.status === 409;
  }
  get isValidation(): boolean {
    return this.status === 400 || this.status === 422;
  }
  get isAuth(): boolean {
    return this.status === 401 || this.status === 403;
  }
  /** Worth offering the user a "Try again" button. */
  get isRetryable(): boolean {
    return (
      this.kind === "network" ||
      this.kind === "offline" ||
      this.kind === "timeout" ||
      (this.status !== null && this.status >= 500)
    );
  }
}

/** Normalise anything thrown into a user-presentable string. Never silent. */
export function toErrorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (error instanceof ApiError) return error.message || fallback;
  if (error instanceof Error) return error.message || fallback;
  if (typeof error === "string" && error.trim()) return error;
  return fallback;
}

/** True when the rejection is just an aborted (superseded/unmounted) request. */
export function isAbortError(error: unknown): boolean {
  if (error instanceof ApiError) return error.isAborted;
  return error instanceof DOMException && error.name === "AbortError";
}

/** Pull the most useful message out of a FastAPI error body. */
function extractMessage(body: unknown): string | null {
  if (typeof body === "string") return body.trim() || null;
  if (!body || typeof body !== "object") return null;

  const detail = (body as { detail?: unknown; message?: unknown }).detail ??
    (body as { message?: unknown }).message;

  if (typeof detail === "string") return detail.trim() || null;

  if (Array.isArray(detail)) {
    // Pydantic validation errors: [{ loc: [...], msg, type }]
    const parts = detail
      .map((entry) => {
        if (typeof entry === "string") return entry;
        if (entry && typeof entry === "object") {
          const { loc, msg } = entry as { loc?: unknown[]; msg?: string };
          const field = Array.isArray(loc)
            ? loc.filter((p) => p !== "body" && p !== "query").join(".")
            : "";
          if (field && msg) return `${field}: ${msg}`;
          if (msg) return msg;
        }
        return null;
      })
      .filter((part): part is string => Boolean(part));
    if (parts.length > 0) return parts.join("; ");
  }

  return null;
}

export interface RequestOptions {
  /** Caller-owned cancellation (component unmount, superseded request, …). */
  signal?: AbortSignal;
  /** Defaults to {@link DEFAULT_TIMEOUT_MS}. */
  timeoutMs?: number;
  headers?: HeadersInit;
  /** Serialised into the query string; `undefined` / `null` values are dropped. */
  query?: Record<string, string | number | boolean | null | undefined>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  // NOTE: `path` is used verbatim. Object ids (`obj:course:AB12…`) are legal
  // path characters — encoding them here would double-encode the id and the
  // backend `ObjectId.parse` would reject `obj%3Acourse%3A…`.
  if (!query) return `${API_BASE_URL}${path}`;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    search.append(key, String(value));
  }
  const qs = search.toString();
  return qs ? `${API_BASE_URL}${path}?${qs}` : `${API_BASE_URL}${path}`;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  options: RequestOptions = {},
): Promise<T> {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    throw new ApiError("You appear to be offline. Check your connection and try again.", {
      kind: "offline",
    });
  }

  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const external = options.signal;
  const forwardAbort = () => controller.abort();
  if (external) {
    if (external.aborted) controller.abort();
    else external.addEventListener("abort", forwardAbort);
  }

  const hasBody = init.body !== undefined && init.body !== null;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (hasBody) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(buildUrl(path, options.query), {
      ...init,
      signal: controller.signal,
      headers: { ...headers, ...(options.headers as Record<string, string> | undefined) },
    });
  } catch (error) {
    if (external?.aborted) {
      throw new ApiError("Request cancelled.", { kind: "aborted" });
    }
    if (timedOut) {
      throw new ApiError(
        `The server did not respond within ${Math.round(timeoutMs / 1000)}s. Please try again.`,
        { kind: "timeout" },
      );
    }
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      throw new ApiError("You appear to be offline. Check your connection and try again.", {
        kind: "offline",
      });
    }
    throw new ApiError(
      `Cannot reach the API at ${API_BASE_URL}. Make sure the backend is running.`,
      { kind: "network", details: error },
    );
  } finally {
    clearTimeout(timer);
    external?.removeEventListener("abort", forwardAbort);
  }

  if (!res.ok) {
    let body: unknown = null;
    try {
      const text = await res.text();
      body = text ? (JSON.parse(text) as unknown) : null;
    } catch {
      /* non-JSON error body — fall back to the status message */
    }
    const message =
      extractMessage(body) ??
      STATUS_FALLBACK[res.status] ??
      `Request failed: ${res.status} ${res.statusText}`;
    throw new ApiError(message, { kind: "http", status: res.status, details: body });
  }

  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }

  const text = await res.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError("The server returned a malformed response.", {
      kind: "http",
      status: res.status,
      details: text,
    });
  }
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, { method: "GET" }, options),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(
      path,
      { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) },
      options,
    ),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(
      path,
      { method: "PUT", body: body === undefined ? undefined : JSON.stringify(body) },
      options,
    ),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { method: "DELETE" }, options),
};

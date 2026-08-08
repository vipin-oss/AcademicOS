import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * M14 — Search reliability. Pins the request-lifecycle contract of the global
 * Search page:
 *  - an aborted (superseded) request must NEVER surface "Request cancelled.";
 *  - the latest query wins (a stale resolved result never overwrites it);
 *  - genuine backend failures ARE shown;
 *  - empty results show a clean empty state, not a cancellation/error.
 *
 * `searchObjects` is mocked so each test controls resolve/reject timing; the
 * REAL client (`ApiError`, `isAbortError`, `toErrorMessage`) is used so the
 * abort error shapes are identical to production.
 */
vi.mock("@/lib/api/search", () => ({
  searchObjects: vi.fn(),
}));

import { searchObjects } from "@/lib/api/search";
import type { SearchHit, SearchResponse } from "@/lib/api/search";
import { ApiError } from "@/lib/api/client";
import SearchPage from "./SearchPage";

const mockedSearch = vi.mocked(searchObjects);

function hit(object_id: string, title: string): SearchHit {
  return {
    object_id,
    object_type: "document",
    title,
    version: 1,
    index_source: "lexical",
    score: 0.016129,
  };
}

/** A controllable promise so tests resolve/reject in deterministic order. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const INPUT_LABEL = "Search objects";

async function type(input: HTMLElement, value: string) {
  fireEvent.change(input, { target: { value } });
}

describe("SearchPage", () => {
  beforeEach(() => {
    mockedSearch.mockReset();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows results for a matching query", async () => {
    mockedSearch.mockResolvedValue({ results: [hit("obj:document:A", "Energy Paper")] });

    render(<SearchPage />);
    await type(screen.getByLabelText(INPUT_LABEL), "energy");

    await waitFor(() =>
      expect(screen.getByText("Energy Paper")).toBeInTheDocument(),
    );
    expect(mockedSearch).toHaveBeenCalledWith(
      { text: "energy", limit: 50 },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("shows a clean empty state — NOT 'Request cancelled.' — when there are no results", async () => {
    mockedSearch.mockResolvedValue({ results: [] });

    render(<SearchPage />);
    await type(screen.getByLabelText(INPUT_LABEL), "energy");

    await waitFor(() =>
      expect(screen.getByText(/No results for/)).toBeInTheDocument(),
    );
    expect(screen.queryByText("Request cancelled.")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("suppresses a superseded request's abort — never shows 'Request cancelled.'", async () => {
    // The client reports a caller-aborted request as
    // ApiError("Request cancelled.", { kind: "aborted" }). The OLD code only
    // checked `err.name === "AbortError"` (false for ApiError) and leaked the
    // message to the UI. It must stay silent.
    mockedSearch
      .mockRejectedValueOnce(new ApiError("Request cancelled.", { kind: "aborted" }))
      .mockResolvedValueOnce({ results: [hit("obj:document:B", "B Wins")] });

    render(<SearchPage />);
    const input = screen.getByLabelText(INPUT_LABEL);
    await type(input, "ene");
    await waitFor(() => expect(mockedSearch).toHaveBeenCalledTimes(1));
    await type(input, "energy");
    await waitFor(() => expect(mockedSearch).toHaveBeenCalledTimes(2));

    await waitFor(() => expect(screen.getByText("B Wins")).toBeInTheDocument());
    expect(screen.queryByText("Request cancelled.")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("also suppresses a DOMException AbortError (the other abort shape)", async () => {
    mockedSearch
      .mockRejectedValueOnce(new DOMException("aborted", "AbortError"))
      .mockResolvedValueOnce({ results: [] });

    render(<SearchPage />);
    const input = screen.getByLabelText(INPUT_LABEL);
    await type(input, "ene");
    await waitFor(() => expect(mockedSearch).toHaveBeenCalledTimes(1));
    await type(input, "energy");
    await waitFor(() => expect(mockedSearch).toHaveBeenCalledTimes(2));

    expect(screen.queryByText("Request cancelled.")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("latest query wins — a stale resolved result does not overwrite the newer query", async () => {
    const a = deferred<SearchResponse>();
    const b = deferred<SearchResponse>();
    mockedSearch.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);

    render(<SearchPage />);
    const input = screen.getByLabelText(INPUT_LABEL);
    await type(input, "ene");
    await waitFor(() => expect(mockedSearch).toHaveBeenCalledTimes(1)); // A in flight
    await type(input, "energy");
    await waitFor(() => expect(mockedSearch).toHaveBeenCalledTimes(2)); // B supersedes A

    // B (the latest) resolves first — its result must be shown.
    await act(async () => {
      b.resolve({ results: [hit("obj:document:B", "B Latest")] });
    });
    await waitFor(() => expect(screen.getByText("B Latest")).toBeInTheDocument());

    // A resolves later with stale data — must NOT overwrite B.
    await act(async () => {
      a.resolve({ results: [hit("obj:document:A", "A Stale")] });
    });
    expect(screen.queryByText("A Stale")).not.toBeInTheDocument();
    expect(screen.getByText("B Latest")).toBeInTheDocument();
  });

  it("shows a genuine backend error (distinguished from cancellation)", async () => {
    mockedSearch.mockRejectedValue(
      new ApiError("The server encountered an unexpected error.", {
        kind: "http",
        status: 500,
      }),
    );

    render(<SearchPage />);
    await type(screen.getByLabelText(INPUT_LABEL), "energy");

    await waitFor(() =>
      expect(screen.getByText(/unexpected error/)).toBeInTheDocument(),
    );
  });
});

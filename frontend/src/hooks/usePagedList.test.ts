import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { usePagedList } from "./usePagedList";

interface Row {
  id: string;
}

interface Filters {
  department?: string | null;
  status?: string | null;
}

function makeFetcher() {
  return vi.fn(
    async (
      request: { page: number; pageSize: number; q?: string } & Filters,
      _signal?: AbortSignal,
    ) => ({
      items: [
        { id: `row-${request.page}-1` },
        { id: `row-${request.page}-2` },
      ] as Row[],
      total_count: 5,
    }),
  );
}

type Options = Parameters<typeof usePagedList<Row, Filters>>[0];

function render(options: Options) {
  return renderHook((props: Options) => usePagedList<Row, Filters>(props), {
    initialProps: options,
  });
}

describe("usePagedList", () => {
  it("fetches page 1 on mount with page/pageSize/q omitted when no search", async () => {
    const fetcher = makeFetcher();
    render({
      pageSize: 10,
      params: { department: "cs" },
      fetcher,
    });

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    expect(fetcher).toHaveBeenCalledWith(
      { department: "cs", page: 1, pageSize: 10, q: undefined },
      expect.any(AbortSignal),
    );
  });

  it("exposes items, total and totalPages from the response", async () => {
    const fetcher = makeFetcher();
    const { result } = render({ pageSize: 2, fetcher });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.items).toHaveLength(2);
    expect(result.current.total).toBe(5);
    expect(result.current.totalPages).toBe(3);
    expect(result.current.page).toBe(1);
    expect(result.current.error).toBeNull();
  });

  it("does not refetch when the caller re-renders with a new options object", async () => {
    const fetcher = makeFetcher();
    const { rerender } = render({ pageSize: 10, search: "", fetcher });

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    rerender({ pageSize: 10, search: "", fetcher });
    rerender({ pageSize: 10, search: "", fetcher });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("debounces the search and includes the trimmed q", async () => {
    vi.useFakeTimers();
    try {
      const fetcher = makeFetcher();
      const { rerender } = render({ pageSize: 10, search: "", fetcher });

      await act(async () => {
        await Promise.resolve(); // let the initial fetch settle
      });

      rerender({ pageSize: 10, search: "  ml  ", fetcher });
      // Debounce in flight: still the old request.
      expect(fetcher).toHaveBeenCalledTimes(1);

      await act(async () => {
        vi.advanceTimersByTime(300);
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(fetcher).toHaveBeenCalledTimes(2);
      expect(fetcher).toHaveBeenLastCalledWith(
        { page: 1, pageSize: 10, q: "ml" },
        expect.any(AbortSignal),
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it("resets to page 1 when a filter changes", async () => {
    const fetcher = makeFetcher();
    let filters: Filters = { department: null };
    const { result, rerender } = render({
      pageSize: 2,
      filterValues: [filters.department],
      params: filters,
      fetcher,
    });

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    act(() => {
      result.current.setPage(3);
    });
    await waitFor(() =>
      expect(fetcher).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 3 }),
        expect.any(AbortSignal),
      ),
    );

    filters = { department: "physics" };
    rerender({
      pageSize: 2,
      filterValues: [filters.department],
      params: filters,
      fetcher,
    });

    await waitFor(() =>
      expect(fetcher).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 1, department: "physics" }),
        expect.any(AbortSignal),
      ),
    );
  });

  it("reports searchActive and filterActive", async () => {
    const fetcher = makeFetcher();
    const { result } = render({
      pageSize: 10,
      search: "ml",
      filterValues: ["  ", "physics"],
      fetcher,
    });

    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(result.current.searchActive).toBe(true);
    // Whitespace-only strings are not "active"; non-empty strings are.
    expect(result.current.filterActive).toBe(true);

    const bare = render({
      pageSize: 10,
      search: "",
      filterValues: ["  ", null],
      fetcher,
    });
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(bare.result.current.searchActive).toBe(false);
    expect(bare.result.current.filterActive).toBe(false);
  });

  it("keeps previous rows on error by default and reports the message", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ items: [{ id: "a" }], total_count: 1 })
      .mockRejectedValueOnce(new Error("boom"));

    const { result } = render({ pageSize: 10, fetcher });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.items).toEqual([{ id: "a" }]);

    act(() => {
      result.current.refresh();
    });
    await waitFor(() => expect(result.current.error).toBe("boom"));
    // Default: rows are kept.
    expect(result.current.items).toEqual([{ id: "a" }]);
    expect(result.current.loading).toBe(false);
  });

  it("clears rows on error when clearOnError is set", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ items: [{ id: "a" }], total_count: 1 })
      .mockRejectedValueOnce(new Error("boom"));

    const { result } = render({ pageSize: 10, clearOnError: true, fetcher });
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.refresh();
    });
    await waitFor(() => expect(result.current.error).toBe("boom"));
    expect(result.current.items).toEqual([]);
  });

  it("refresh() re-fetches and sets refreshing while keeping rows", async () => {
    const fetcher = makeFetcher();
    const { result } = render({ pageSize: 2, fetcher });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    act(() => {
      result.current.refresh();
    });
    expect(result.current.refreshing).toBe(true);
    expect(result.current.items).toHaveLength(2); // old rows kept

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    expect(result.current.refreshing).toBe(false);
  });

  it("settles a stranded page back to the last valid page", async () => {
    const fetcher = vi.fn(
      async (request: { page: number; pageSize: number }) => ({
        items: [{ id: `row-${request.page}` }],
        // Page 2 exists only in the first response; after refresh the
        // dataset shrinks to one page.
        total_count: request.page === 1 ? 3 : 1,
      }),
    );

    const { result } = render({ pageSize: 2, fetcher });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    act(() => {
      result.current.setPage(2);
    });
    await waitFor(() =>
      expect(fetcher).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 2 }),
        expect.any(AbortSignal),
      ),
    );

    act(() => {
      result.current.refresh();
    });
    await waitFor(() =>
      expect(fetcher).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 1 }),
        expect.any(AbortSignal),
      ),
    );
    expect(result.current.page).toBe(1);
  });

  it("aborts the in-flight request when the query changes", async () => {
    const fetcher = makeFetcher();
    const { rerender } = render({ pageSize: 10, search: "", fetcher });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    const firstSignal = fetcher.mock.calls[0][1] as AbortSignal;
    expect(firstSignal.aborted).toBe(false);

    rerender({ pageSize: 10, search: "x", fetcher });
    // The debounce elapses in real time (~300ms); the request change then
    // aborts the superseded fetch.
    await waitFor(() => expect(firstSignal.aborted).toBe(true));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });
});

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { isAbortError, toErrorMessage } from "@/lib/api/client";

/**
 * Shared list view-state (R6 — reusable frontend list framework).
 *
 * One state machine for every paginated, searchable, filterable list in the
 * app. Entity hooks become thin wrappers that supply their page size, their
 * filter values, their request params and their API fetcher; the framework
 * owns the mechanics:
 *
 * - server pagination (`page` / `pageSize` / `totalPages`),
 * - debounced server-side search (`search` is debounced internally),
 * - reset-to-page-1 whenever the query or any filter changes,
 * - first-load `loading` vs background `refreshing` (keep old rows while a
 *   page change / refresh is in flight),
 * - request abort on unmount and on supersession,
 * - `refresh()` for post-CRUD reloads,
 * - a stranded-page guard: after a delete shrinks the dataset, a page past
 *   the end settles on the last valid page instead of showing a blank page.
 *
 * Behaviour notes (evidence-backed defaults):
 * - on error the previous rows are kept; pass `clearOnError` to drop them
 *   (the publications/documents/objects hooks clear).
 * - `isSearching` is true while the user is still typing or while a
 *   search/filter request is refreshing (the faculty/students semantics).
 *
 * The caller MUST memoize `params` (useMemo over the filter values) so the
 * request is rebuilt exactly when a filter changes — never on every render.
 * The fetcher and option flags are read through a ref, so they may be
 * inline values without causing refetch loops.
 */
export interface PagedListParams {
  page: number;
  pageSize: number;
  /** Debounced, trimmed search text (omitted when empty). */
  q?: string;
}

export interface PagedListResponse<TItem> {
  items: TItem[];
  total_count: number;
}

export interface UsePagedListOptions<TItem, TParams extends object> {
  pageSize: number;
  /** Raw (undebounced) search text — the hook debounces it internally. */
  search?: string;
  searchDelay?: number;
  /**
   * Filter values that reset pagination to page 1 when they change and
   * drive `filterActive` (strings are trimmed before the truthiness check).
   */
  filterValues?: unknown[];
  /** Caller-owned filter params, memoized, merged into every request. */
  params?: TParams;
  /** Drop the previous rows when a request fails (default: keep them). */
  clearOnError?: boolean;
  /** Fallback message when the error carries no usable text. */
  errorFallback?: string;
  fetcher: (
    params: TParams & PagedListParams,
    signal: AbortSignal,
  ) => Promise<PagedListResponse<TItem>>;
}

export interface UsePagedListResult<TItem> {
  items: TItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  /** First load / hard reload: render skeletons. */
  loading: boolean;
  /** Background reload (page change, refresh after CRUD): keep the old rows. */
  refreshing: boolean;
  error: string | null;
  /** True while the user is still typing or the filtered request is in flight. */
  isSearching: boolean;
  searchActive: boolean;
  filterActive: boolean;
  setPage: (page: number) => void;
  refresh: () => void;
}

export function usePagedList<TItem, TParams extends object>(
  options: UsePagedListOptions<TItem, TParams>,
): UsePagedListResult<TItem> {
  const {
    pageSize,
    search = "",
    searchDelay = 300,
    filterValues = [],
    params,
    clearOnError = false,
    errorFallback = "Something went wrong.",
    fetcher,
  } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;
  const filterActive = filterValues.some((value) =>
    typeof value === "string" ? value.trim().length > 0 : value != null,
  );

  const [page, setPage] = useState(1);
  const [data, setData] = useState<PagedListResponse<TItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  // The fetch effect re-runs only when the request or reloadToken changes,
  // exactly like the per-entity hooks this framework replaces. The option
  // values live in a ref so callers may pass inline functions/literals
  // without triggering a refetch on every render.
  const optionsRef = useRef({ fetcher, clearOnError, errorFallback });
  optionsRef.current = { fetcher, clearOnError, errorFallback };

  // A new query or filter always starts on page 1.
  useEffect(() => {
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- filterValues is
    // the caller's reset contract; its identity is stable per render.
  }, [debouncedSearch, ...filterValues]);

  const request = useMemo(
    () =>
      ({
        ...params,
        page,
        pageSize,
        q: debouncedSearch || undefined,
      }) as TParams & PagedListParams,
    [params, page, pageSize, debouncedSearch],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const { fetcher: run, clearOnError: dropRows, errorFallback: fallback } =
      optionsRef.current;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    run(request, controller.signal)
      .then((response) => {
        if (!active) return;
        hasDataRef.current = true;
        setData(response);
      })
      .catch((err: unknown) => {
        if (!active || isAbortError(err)) return;
        if (dropRows) {
          hasDataRef.current = false;
          setData(null);
        }
        setError(toErrorMessage(err, fallback));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
        setRefreshing(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [request, reloadToken]);

  const total = data?.total_count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Deleting the last row of the last page must not leave us stranded.
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);

  return {
    items: data?.items ?? [],
    total,
    page,
    pageSize,
    totalPages,
    loading,
    refreshing,
    error,
    isSearching:
      searchActive && (trimmedSearch !== debouncedSearch || refreshing),
    searchActive,
    filterActive,
    setPage,
    refresh,
  };
}

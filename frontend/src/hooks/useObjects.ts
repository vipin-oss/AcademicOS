"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, toErrorMessage } from "@/lib/api/client";
import { listObjects } from "@/lib/api/objects";
import { DEFAULT_PAGE_SIZE, SEARCH_WINDOW_SIZE } from "@/lib/objects/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type { ListObjectsResponse, ObjectResponse } from "@/types";

export interface UseObjectsOptions {
  pageSize?: number;
  /** Raw (undebounced) search text — the hook debounces it internally. */
  search?: string;
  searchDelay?: number;
}

export interface UseObjectsResult {
  items: ObjectResponse[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  /** First load / hard reload: render skeletons. */
  loading: boolean;
  /** Background reload (page change, refresh after CRUD): keep the old rows. */
  refreshing: boolean;
  error: string | null;
  /** True while the user is still typing or the search window is loading. */
  isSearching: boolean;
  searchActive: boolean;
  /** The search window did not cover the whole dataset (needs backend search). */
  searchTruncated: boolean;
  setPage: (page: number) => void;
  refresh: () => void;
}

/** Short tokens are not matched against the id — random hex would match "1". */
const MIN_ID_TOKEN_LENGTH = 4;

/** Case-insensitive AND-match across every searchable field, incl. metadata. */
function matchesQuery(object: ObjectResponse, query: string): boolean {
  const haystack = [
    object.title,
    object.object_type,
    object.created_by,
    object.status,
    ...Object.entries(object.metadata ?? {}).flat(),
  ]
    .join(" ")
    .toLowerCase();

  const id = object.id.toLowerCase();

  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every(
      (token) =>
        haystack.includes(token) ||
        (token.length >= MIN_ID_TOKEN_LENGTH && id.includes(token)),
    );
}

/**
 * Objects list state: server pagination + debounced search + refresh.
 *
 * Search note: the backend exposes no `q` parameter yet, so a search fetches a
 * single window of up to {@link SEARCH_WINDOW_SIZE} objects and filters in
 * memory (instant, zero requests per keystroke). Paging inside a search result
 * issues NO request at all. See `searchTruncated`.
 *
 * Accepts a plain page size (`useObjects(12)`) for backwards compatibility.
 */
export function useObjects(options: number | UseObjectsOptions = {}): UseObjectsResult {
  const normalised: UseObjectsOptions = typeof options === "number" ? { pageSize: options } : options;
  const { pageSize = DEFAULT_PAGE_SIZE, search = "", searchDelay = 300 } = normalised;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListObjectsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  // A new query always starts on page 1.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, pageSize]);

  /**
   * What we actually ask the server for. Encoded as a string first so that
   * paging *within* a client-side search result does not change the identity
   * of the request and therefore triggers no refetch.
   */
  const requestKey = searchActive ? `1:${SEARCH_WINDOW_SIZE}` : `${page}:${pageSize}`;
  const request = useMemo(() => {
    const [requestPage, requestSize] = requestKey.split(":").map(Number);
    return { page: requestPage, pageSize: requestSize };
  }, [requestKey]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    listObjects(
      { page: request.page, pageSize: request.pageSize },
      { signal: controller.signal },
    )
      .then((response) => {
        if (!active) return;
        hasDataRef.current = true;
        setData(response);
      })
      .catch((err: unknown) => {
        if (!active || (err instanceof ApiError && err.isAborted)) return;
        hasDataRef.current = false;
        setData(null);
        setError(toErrorMessage(err, "Failed to load objects."));
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

  const allItems = useMemo(() => data?.items ?? [], [data]);

  const filtered = useMemo(
    () => (searchActive ? allItems.filter((object) => matchesQuery(object, debouncedSearch)) : allItems),
    [allItems, searchActive, debouncedSearch],
  );

  const total = searchActive ? filtered.length : data?.total_count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Deleting the last row of the last page must not leave us stranded.
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const items = useMemo(
    () => (searchActive ? filtered.slice((page - 1) * pageSize, page * pageSize) : filtered),
    [searchActive, filtered, page, pageSize],
  );

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);
console.log({
  search,
  trimmedSearch,
  debouncedSearch,
  searchActive,
  totalItems: allItems.length,
  filteredItems: filtered.length,
});

  return {
    items,
    total,
    page,
    pageSize,
    totalPages,
    loading,
    refreshing,
    error,
    isSearching: trimmedSearch !== debouncedSearch || (searchActive && (loading || refreshing)),
    searchActive,
    searchTruncated: searchActive && (data?.total_count ?? 0) > SEARCH_WINDOW_SIZE,
    setPage,
    refresh,
  };
}

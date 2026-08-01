"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, toErrorMessage } from "@/lib/api/client";
import { listDocuments } from "@/lib/api/documents";
import {
  DEFAULT_DOC_PAGE_SIZE,
  SEARCH_WINDOW_SIZE,
} from "@/lib/documents/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type {
  DocumentResponse,
  DocumentStatus,
  DocumentTypeValue,
  ListDocumentsResponse,
} from "@/types";

export interface UseDocumentsOptions {
  pageSize?: number;
  /** Raw (undebounced) search text — the hook debounces it internally. */
  search?: string;
  searchDelay?: number;
  /** Client-side type filter (`"all"` disables it). */
  type?: DocumentTypeValue | "all";
  /** Client-side status filter (`"all"` disables it). */
  status?: DocumentStatus | "all";
}

export interface UseDocumentsResult {
  items: DocumentResponse[];
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
  /** The search/filter window did not cover the whole dataset (needs backend). */
  searchTruncated: boolean;
  setPage: (page: number) => void;
  refresh: () => void;
}

/** Case-insensitive AND-match across every searchable field, incl. tags. */
function matchesQuery(document: DocumentResponse, query: string): boolean {
  const haystack = [
    document.title,
    document.document_type,
    document.object_title ?? document.object_id ?? "",
    document.uploaded_by,
    document.status,
    document.description ?? "",
    ...document.tags,
  ]
    .join(" ")
    .toLowerCase();

  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((token) => haystack.includes(token));
}

function passesFilters(
  document: DocumentResponse,
  type: DocumentTypeValue | "all",
  status: DocumentStatus | "all",
): boolean {
  if (type !== "all" && document.document_type !== type) return false;
  if (status !== "all" && document.status !== status) return false;
  return true;
}

/**
 * Documents list state: server pagination + debounced search + type/status
 * filters + refresh.
 *
 * Like the Objects module, the backend exposes no `q`/`type`/`status`
 * parameters yet, so a search/filter fetches a single window of up to
 * {@link SEARCH_WINDOW_SIZE} documents and filters in memory (instant, zero
 * requests per keystroke). Paging inside a filtered result issues NO request.
 */
export function useDocuments(
  options: UseDocumentsOptions = {},
): UseDocumentsResult {
  const {
    pageSize = DEFAULT_DOC_PAGE_SIZE,
    search = "",
    searchDelay = 300,
    type = "all",
    status = "all",
  } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;
  const filtering = searchActive || type !== "all" || status !== "all";

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListDocumentsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  // A new query or filter always starts on page 1.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, type, status]);

  const requestKey = filtering ? `1:${SEARCH_WINDOW_SIZE}` : `${page}:${pageSize}`;
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

    listDocuments(
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
        setError(toErrorMessage(err, "Failed to load documents."));
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
    () =>
      filtering
        ? allItems.filter(
            (document) =>
              passesFilters(document, type, status) &&
              (!searchActive || matchesQuery(document, debouncedSearch)),
          )
        : allItems,
    [allItems, filtering, type, status, searchActive, debouncedSearch],
  );

  const total = filtering ? filtered.length : data?.total_count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Deleting the last row of the last page must not leave us stranded.
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const items = useMemo(
    () => (filtering ? filtered.slice((page - 1) * pageSize, page * pageSize) : filtered),
    [filtering, filtered, page, pageSize],
  );

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);

  return {
    items,
    total,
    page,
    pageSize,
    totalPages,
    loading,
    refreshing,
    error,
    isSearching:
      trimmedSearch !== debouncedSearch || (filtering && (loading || refreshing)),
    searchActive,
    searchTruncated: filtering && (data?.total_count ?? 0) > SEARCH_WINDOW_SIZE,
    setPage,
    refresh,
  };
}

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, toErrorMessage } from "@/lib/api/client";
import { listPublications } from "@/lib/api/publications";
import { DEFAULT_PUB_PAGE_SIZE } from "@/lib/publications/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type {
  ListPublicationsResponse,
  PipelineStage,
  PublicationResponse,
  PublicationStatus,
  PublicationTypeValue,
  Quartile,
} from "@/types";

export interface UsePublicationsOptions {
  pageSize?: number;
  /** Raw (undebounced) search text — the hook debounces it internally. */
  search?: string;
  searchDelay?: number;
  /** Server-side filters (`null` disables each). */
  type?: PublicationTypeValue | null;
  year?: number | null;
  quartile?: Quartile | null;
  pipelineStage?: PipelineStage | null;
  status?: PublicationStatus | null;
  /** Object lens ("papers linked to X") — pins the list to one Object. */
  objectId?: string | null;
}

export interface UsePublicationsResult {
  items: PublicationResponse[];
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

/**
 * Publications list state: server pagination + debounced server-side search +
 * server-side filters + refresh.
 *
 * Unlike `useDocuments` (which filters client-side because the backend grew
 * search later), the Publications API was designed with `q` and the exact
 * filters the reference-manager UI needs — so this hook stays a thin state
 * machine: debounce -> request -> render. No search window, no truncation.
 */
export function usePublications(
  options: UsePublicationsOptions = {},
): UsePublicationsResult {
  const {
    pageSize = DEFAULT_PUB_PAGE_SIZE,
    search = "",
    searchDelay = 300,
    type = null,
    year = null,
    quartile = null,
    pipelineStage = null,
    status = null,
    objectId = null,
  } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;
  const filterActive = Boolean(
    type || year != null || quartile || pipelineStage || status,
  );

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListPublicationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  // A new query or filter always starts on page 1.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, type, year, quartile, pipelineStage, status, objectId]);

  const request = useMemo(
    () => ({
      page,
      pageSize,
      q: debouncedSearch || undefined,
      publicationType: type ?? undefined,
      year: year ?? undefined,
      quartile: quartile ?? undefined,
      pipelineStage: pipelineStage ?? undefined,
      status: status ?? undefined,
      objectId: objectId ?? undefined,
    }),
    [page, pageSize, debouncedSearch, type, year, quartile, pipelineStage, status, objectId],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    listPublications(request, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        hasDataRef.current = true;
        setData(response);
      })
      .catch((err: unknown) => {
        if (!active || (err instanceof ApiError && err.isAborted)) return;
        hasDataRef.current = false;
        setData(null);
        setError(toErrorMessage(err, "Failed to load publications."));
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
    items: useMemo(() => data?.items ?? [], [data]),
    total,
    page,
    pageSize,
    totalPages,
    loading,
    refreshing,
    error,
    isSearching:
      trimmedSearch !== debouncedSearch || ((searchActive || filterActive) && refreshing),
    searchActive,
    filterActive,
    setPage,
    refresh,
  };
}

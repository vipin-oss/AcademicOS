"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listProjects } from "@/lib/api/research";
import { DEFAULT_PROJECT_PAGE_SIZE } from "@/lib/research/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type { ListProjectsResponse, ProjectLifecycleStatus, ProjectResponse } from "@/types";

export interface UseProjectsOptions {
  pageSize?: number;
  /** Raw (undebounced) search text — the hook debounces it internally. */
  search?: string;
  searchDelay?: number;
  /** PART 9 server-side filters (`null` disables each). */
  pi?: string | null;
  agency?: string | null;
  status?: ProjectLifecycleStatus | null;
  year?: number | null;
  department?: string | null;
  /** Object lens ("projects linked to X") — pins the list to one Object. */
  objectId?: string | null;
}

export interface UseProjectsResult {
  items: ProjectResponse[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  isSearching: boolean;
  searchActive: boolean;
  filterActive: boolean;
  setPage: (page: number) => void;
  refresh: () => void;
}

/** Projects list state — mirrors `useStudents` / `useClasses` one-to-one. */
export function useProjects(options: UseProjectsOptions = {}): UseProjectsResult {
  const {
    pageSize = DEFAULT_PROJECT_PAGE_SIZE,
    search = "",
    searchDelay = 300,
    pi = null,
    agency = null,
    status = null,
    year = null,
    department = null,
    objectId = null,
  } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;
  const filterActive = Boolean(
    pi?.trim() || agency?.trim() || status || year != null || department?.trim(),
  );

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListProjectsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  // A new query or filter always starts on page 1.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, pi, agency, status, year, department, objectId]);

  const request = useMemo(
    () => ({
      page,
      pageSize,
      q: debouncedSearch || undefined,
      pi: pi?.trim() || null,
      agency: agency?.trim() || null,
      status: status ?? null,
      year: year ?? null,
      department: department?.trim() || null,
      objectId: objectId ?? null,
    }),
    [page, pageSize, debouncedSearch, pi, agency, status, year, department, objectId],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    listProjects(request, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setData(response);
        hasDataRef.current = true;
      })
      .catch((err) => {
        if (!active || err?.name === "AbortError") return;
        setError(toErrorMessage(err));
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

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);

  return {
    items: data?.items ?? [],
    total: data?.total_count ?? 0,
    page,
    pageSize,
    totalPages: Math.max(1, Math.ceil((data?.total_count ?? 0) / pageSize)),
    loading,
    refreshing,
    error,
    isSearching:
      trimmedSearch.length > 0 && (trimmedSearch !== debouncedSearch || refreshing),
    searchActive,
    filterActive,
    setPage,
    refresh,
  };
}

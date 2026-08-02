"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listClasses } from "@/lib/api/teaching";
import { DEFAULT_CLASS_PAGE_SIZE } from "@/lib/teaching/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type { ClassResponse, ClassStatus, ListClassesResponse } from "@/types";

export interface UseClassesOptions {
  pageSize?: number;
  search?: string;
  searchDelay?: number;
  semester?: number | null;
  session?: string | null;
  status?: ClassStatus | null;
  objectId?: string | null;
}

export interface UseClassesResult {
  items: ClassResponse[];
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

/** Classes list state — mirrors `useStudents` / `usePublications`. */
export function useClasses(options: UseClassesOptions = {}): UseClassesResult {
  const {
    pageSize = DEFAULT_CLASS_PAGE_SIZE,
    search = "",
    searchDelay = 300,
    semester = null,
    session = null,
    status = null,
    objectId = null,
  } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;
  const filterActive = Boolean(semester != null || session?.trim() || status);

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListClassesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, semester, session, status, objectId]);

  const request = useMemo(
    () => ({
      page,
      pageSize,
      q: debouncedSearch || undefined,
      semester: semester ?? undefined,
      session: session?.trim() || undefined,
      status: status ?? undefined,
      objectId: objectId ?? undefined,
    }),
    [page, pageSize, debouncedSearch, semester, session, status, objectId],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    listClasses(request, { signal: controller.signal })
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
    isSearching: trimmedSearch.length > 0 && (trimmedSearch !== debouncedSearch || refreshing),
    searchActive,
    filterActive,
    setPage,
    refresh,
  };
}

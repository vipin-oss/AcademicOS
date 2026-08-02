"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listAgencies } from "@/lib/api/research";
import { DEFAULT_AGENCY_PAGE_SIZE } from "@/lib/research/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type { AgencyResponse, ListAgenciesResponse, ResearchObjectStatus } from "@/types";

export interface UseAgenciesOptions {
  pageSize?: number;
  search?: string;
  searchDelay?: number;
  status?: ResearchObjectStatus | null;
}

export interface UseAgenciesResult {
  items: AgencyResponse[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  isSearching: boolean;
  setPage: (page: number) => void;
  refresh: () => void;
}

/** Funding-agency registry state — mirrors `useGrants`. */
export function useAgencies(options: UseAgenciesOptions = {}): UseAgenciesResult {
  const {
    pageSize = DEFAULT_AGENCY_PAGE_SIZE,
    search = "",
    searchDelay = 300,
    status = null,
  } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListAgenciesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, status]);

  const request = useMemo(
    () => ({
      page,
      pageSize,
      q: debouncedSearch || undefined,
      status: status ?? null,
    }),
    [page, pageSize, debouncedSearch, status],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    listAgencies(request, { signal: controller.signal })
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
    setPage,
    refresh,
  };
}

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listVendors } from "@/lib/api/finance";
import { DEFAULT_VENDOR_PAGE_SIZE } from "@/lib/finance/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type { ListVendorsResponse, VendorResponse } from "@/types";

export interface UseVendorsOptions {
  pageSize?: number;
  /** Raw (undebounced) search text — the hook debounces it internally. */
  search?: string;
  searchDelay?: number;
}

export interface UseVendorsResult {
  items: VendorResponse[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  isSearching: boolean;
  searchActive: boolean;
  setPage: (page: number) => void;
  refresh: () => void;
}

/** Vendor registry list state — mirrors `useCommittees` one-to-one. */
export function useVendors(options: UseVendorsOptions = {}): UseVendorsResult {
  const { pageSize = DEFAULT_VENDOR_PAGE_SIZE, search = "", searchDelay = 300 } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListVendorsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  const request = useMemo(
    () => ({ page, pageSize, q: debouncedSearch || undefined }),
    [page, pageSize, debouncedSearch],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    listVendors(request, { signal: controller.signal })
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
    isSearching: trimmedSearch.length > 0 && debouncedSearch !== trimmedSearch,
    searchActive,
    setPage,
    refresh,
  };
}

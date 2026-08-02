"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listAssetRegister } from "@/lib/api/finance";
import { DEFAULT_ASSET_PAGE_SIZE } from "@/lib/finance/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type {
  AssetCategory,
  AssetStatus,
  ListAssetRegisterResponse,
  AssetRegisterRow,
} from "@/types";

export interface UseAssetRegisterOptions {
  pageSize?: number;
  search?: string;
  searchDelay?: number;
  category?: AssetCategory | null;
  status?: AssetStatus | null;
}

export interface UseAssetRegisterResult {
  items: AssetRegisterRow[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  searchActive: boolean;
  filterActive: boolean;
  setPage: (page: number) => void;
  refresh: () => void;
}

/** PART 8 asset register state — mirrors `useCommittees` one-to-one. */
export function useAssetRegister(options: UseAssetRegisterOptions = {}): UseAssetRegisterResult {
  const {
    pageSize = DEFAULT_ASSET_PAGE_SIZE,
    search = "",
    searchDelay = 300,
    category = null,
    status = null,
  } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;
  const filterActive = Boolean(category || status);

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListAssetRegisterResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, category, status]);

  const request = useMemo(
    () => ({
      page,
      pageSize,
      q: debouncedSearch || undefined,
      category: category ?? null,
      status: status ?? null,
    }),
    [page, pageSize, debouncedSearch, category, status],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    listAssetRegister(request, { signal: controller.signal })
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
    searchActive,
    filterActive,
    setPage,
    refresh,
  };
}

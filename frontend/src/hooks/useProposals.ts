"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listProposals } from "@/lib/api/finance";
import { DEFAULT_PROPOSAL_PAGE_SIZE } from "@/lib/finance/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type { ListProposalsResponse, ProposalResponse, ProposalStatus } from "@/types";

export interface UseProposalsOptions {
  pageSize?: number;
  /** Raw (undebounced) search text — the hook debounces it internally. */
  search?: string;
  searchDelay?: number;
  /** PART 12 server-side filters (`null` disables each). */
  vendor?: string | null;
  project?: string | null;
  grant?: string | null;
  status?: ProposalStatus | null;
  department?: string | null;
  financialYear?: string | null;
}

export interface UseProposalsResult {
  items: ProposalResponse[];
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

/** Proposals list state — mirrors `useCommittees` / `useProjects` one-to-one. */
export function useProposals(options: UseProposalsOptions = {}): UseProposalsResult {
  const {
    pageSize = DEFAULT_PROPOSAL_PAGE_SIZE,
    search = "",
    searchDelay = 300,
    vendor = null,
    project = null,
    grant = null,
    status = null,
    department = null,
    financialYear = null,
  } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;
  const filterActive = Boolean(
    vendor?.trim() ||
      project?.trim() ||
      grant?.trim() ||
      status ||
      department?.trim() ||
      financialYear?.trim(),
  );

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListProposalsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  // A new query or filter always starts on page 1.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, vendor, project, grant, status, department, financialYear]);

  const request = useMemo(
    () => ({
      page,
      pageSize,
      q: debouncedSearch || undefined,
      vendor: vendor?.trim() || null,
      project: project?.trim() || null,
      grant: grant?.trim() || null,
      status: status ?? null,
      department: department?.trim() || null,
      financialYear: financialYear?.trim() || null,
    }),
    [page, pageSize, debouncedSearch, vendor, project, grant, status, department, financialYear],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    listProposals(request, { signal: controller.signal })
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
    filterActive,
    setPage,
    refresh,
  };
}

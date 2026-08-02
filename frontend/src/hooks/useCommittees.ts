"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listCommittees } from "@/lib/api/committees";
import { DEFAULT_COMMITTEE_PAGE_SIZE } from "@/lib/committees/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type {
  CommitteeResponse,
  ListCommitteesResponse,
  ResearchObjectStatus,
} from "@/types";

export interface UseCommitteesOptions {
  pageSize?: number;
  /** Raw (undebounced) search text — the hook debounces it internally. */
  search?: string;
  searchDelay?: number;
  /** PART 9 server-side filters (`null` disables each). */
  committeeType?: string | null;
  department?: string | null;
  chairperson?: string | null;
  status?: ResearchObjectStatus | null;
  meetingYear?: number | null;
}

export interface UseCommitteesResult {
  items: CommitteeResponse[];
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

/** Committees list state — mirrors `useProjects` / `useStudents` one-to-one. */
export function useCommittees(options: UseCommitteesOptions = {}): UseCommitteesResult {
  const {
    pageSize = DEFAULT_COMMITTEE_PAGE_SIZE,
    search = "",
    searchDelay = 300,
    committeeType = null,
    department = null,
    chairperson = null,
    status = null,
    meetingYear = null,
  } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;
  const filterActive = Boolean(
    committeeType?.trim() ||
      department?.trim() ||
      chairperson?.trim() ||
      status ||
      meetingYear != null,
  );

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListCommitteesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  // A new query or filter always starts on page 1.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, committeeType, department, chairperson, status, meetingYear]);

  const request = useMemo(
    () => ({
      page,
      pageSize,
      q: debouncedSearch || undefined,
      committeeType: committeeType?.trim() || null,
      department: department?.trim() || null,
      chairperson: chairperson?.trim() || null,
      status: status ?? null,
      meetingYear: meetingYear ?? null,
    }),
    [
      page,
      pageSize,
      debouncedSearch,
      committeeType,
      department,
      chairperson,
      status,
      meetingYear,
    ],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    listCommittees(request, { signal: controller.signal })
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

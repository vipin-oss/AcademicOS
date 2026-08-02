"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listFaculty } from "@/lib/api/faculty";
import { DEFAULT_FACULTY_PAGE_SIZE } from "@/lib/faculty/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type {
  FacultyEmploymentType,
  FacultyResponse,
  ListFacultyResponse,
  ResearchObjectStatus,
} from "@/types";

export interface UseFacultiesOptions {
  pageSize?: number;
  /** Raw (undebounced) search text — the hook debounces it internally. */
  search?: string;
  searchDelay?: number;
  /** PART 7 server-side filters (`null` disables each). */
  department?: string | null;
  designation?: string | null;
  employmentType?: FacultyEmploymentType | null;
  status?: ResearchObjectStatus | null;
}

export interface UseFacultiesResult {
  items: FacultyResponse[];
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

/** Faculty directory list state — mirrors `useProjects` / `useStudents` one-to-one. */
export function useFaculties(options: UseFacultiesOptions = {}): UseFacultiesResult {
  const {
    pageSize = DEFAULT_FACULTY_PAGE_SIZE,
    search = "",
    searchDelay = 300,
    department = null,
    designation = null,
    employmentType = null,
    status = null,
  } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;
  const filterActive = Boolean(
    department?.trim() || designation?.trim() || employmentType || status,
  );

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListFacultyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  // A new query or filter always starts on page 1.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, department, designation, employmentType, status]);

  const request = useMemo(
    () => ({
      page,
      pageSize,
      q: debouncedSearch || undefined,
      department: department?.trim() || null,
      designation: designation?.trim() || null,
      employmentType: employmentType ?? null,
      status: status ?? null,
    }),
    [page, pageSize, debouncedSearch, department, designation, employmentType, status],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    listFaculty(request, { signal: controller.signal })
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

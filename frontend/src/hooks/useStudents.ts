"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listStudents } from "@/lib/api/students";
import { DEFAULT_STUDENT_PAGE_SIZE } from "@/lib/students/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type {
  ListStudentsResponse,
  StudentResponse,
  StudentStatus,
  StudentTypeValue,
} from "@/types";

export interface UseStudentsOptions {
  pageSize?: number;
  /** Raw (undebounced) search text — the hook debounces it internally. */
  search?: string;
  searchDelay?: number;
  /** Server-side filters (`null` disables each). */
  studentType?: StudentTypeValue | null;
  programme?: string | null;
  semester?: number | null;
  section?: string | null;
  status?: StudentStatus | null;
  /** Object lens ("students linked to X") — pins the list to one Object. */
  objectId?: string | null;
}

export interface UseStudentsResult {
  items: StudentResponse[];
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

/**
 * Students list state: server pagination + debounced server-side search +
 * server-side filters + refresh. Thin state machine — mirrors
 * `usePublications` one-to-one.
 */
export function useStudents(options: UseStudentsOptions = {}): UseStudentsResult {
  const {
    pageSize = DEFAULT_STUDENT_PAGE_SIZE,
    search = "",
    searchDelay = 300,
    studentType = null,
    programme = null,
    semester = null,
    section = null,
    status = null,
    objectId = null,
  } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;
  const filterActive = Boolean(
    studentType || programme?.trim() || semester != null || section?.trim() || status,
  );

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListStudentsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  // A new query or filter always starts on page 1.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, studentType, programme, semester, section, status, objectId]);

  const request = useMemo(
    () => ({
      page,
      pageSize,
      q: debouncedSearch || undefined,
      studentType: studentType ?? undefined,
      programme: programme?.trim() || undefined,
      semester: semester ?? undefined,
      section: section?.trim() || undefined,
      status: status ?? undefined,
      objectId: objectId ?? undefined,
    }),
    [page, pageSize, debouncedSearch, studentType, programme, semester, section, status, objectId],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    listStudents(request, { signal: controller.signal })
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

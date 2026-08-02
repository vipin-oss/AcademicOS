"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listEvents } from "@/lib/api/events";
import { DEFAULT_EVENT_PAGE_SIZE } from "@/lib/events/constants";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type {
  EventResponse,
  EventStatus,
  EventType,
  ListEventsResponse,
  ParticipationRole,
} from "@/types";

export interface UseEventsOptions {
  pageSize?: number;
  /** Raw (undebounced) search text — the hook debounces it internally. */
  search?: string;
  searchDelay?: number;
  /** PART 10 server-side filters (`null` disables each). */
  eventType?: EventType | null;
  year?: string | null;
  role?: ParticipationRole | null;
  department?: string | null;
  organizer?: string | null;
  status?: EventStatus | null;
}

export interface UseEventsResult {
  items: EventResponse[];
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

/** Events list state — mirrors `useProposals` / `useCommittees` one-to-one. */
export function useEvents(options: UseEventsOptions = {}): UseEventsResult {
  const {
    pageSize = DEFAULT_EVENT_PAGE_SIZE,
    search = "",
    searchDelay = 300,
    eventType = null,
    year = null,
    role = null,
    department = null,
    organizer = null,
    status = null,
  } = options;

  const trimmedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(trimmedSearch, searchDelay);
  const searchActive = debouncedSearch.length > 0;
  const filterActive = Boolean(
    eventType ||
      year?.trim() ||
      role ||
      department?.trim() ||
      organizer?.trim() ||
      status,
  );

  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListEventsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const hasDataRef = useRef(false);

  // A new query or filter always starts on page 1.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, eventType, year, role, department, organizer, status]);

  const request = useMemo(
    () => ({
      page,
      pageSize,
      q: debouncedSearch || undefined,
      eventType: eventType ?? null,
      year: year?.trim() || null,
      role: role ?? null,
      department: department?.trim() || null,
      organizer: organizer?.trim() || null,
      status: status ?? null,
    }),
    [page, pageSize, debouncedSearch, eventType, year, role, department, organizer, status],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (hasDataRef.current) setRefreshing(true);
    else setLoading(true);
    setError(null);

    listEvents(request, { signal: controller.signal })
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

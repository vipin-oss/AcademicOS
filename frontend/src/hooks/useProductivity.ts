"use client";

/**
 * Productivity Hub data hooks (mirror useReportsDashboard / useReport).
 * Fetch-once hooks with `refresh()` and a debounced search hook.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import {
  getCalendarFeed,
  getProductivityDashboard,
  getReminders,
  listNotifications,
  listTasks,
  searchProductivity,
  type NotificationFilters,
  type TaskFilters,
} from "@/lib/api/productivity";
import type {
  CalendarFeed,
  NotificationListResult,
  ProductivityDashboard,
  ProductivitySearchResult,
  RemindersFeed,
  TaskListResult,
} from "@/types";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

function useAsyncData<T>(loader: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null });
  const [tick, setTick] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    let cancelled = false;
    setState((prev) => ({ ...prev, loading: true, error: null }));
    loaderRef
      .current()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch((err: Error) => {
        if (!cancelled) setState({ data: null, loading: false, error: err.message });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const refresh = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, refresh };
}

export function useProductivityDashboard(asOf?: string) {
  const { data, loading, error, refresh } = useAsyncData<ProductivityDashboard>(
    () => getProductivityDashboard(asOf ? { asOf } : undefined),
    [asOf],
  );
  return { dashboard: data, loading, error, refresh };
}

export function useCalendarFeed(
  dateFrom: string,
  dateTo: string,
  sources?: string[],
  refreshKey = 0,
) {
  const key = (sources ?? []).join(",");
  const { data, loading, error, refresh } = useAsyncData<CalendarFeed>(
    () => getCalendarFeed(dateFrom, dateTo, sources),
    [dateFrom, dateTo, key, refreshKey],
  );
  return { feed: data, loading, error, refresh };
}

export function useReminders() {
  const { data, loading, error, refresh } = useAsyncData<RemindersFeed>(() => getReminders(), []);
  return { reminders: data, loading, error, refresh };
}

export function useTasks(filters: TaskFilters) {
  const key = JSON.stringify(filters);
  const { data, loading, error, refresh } = useAsyncData<TaskListResult>(() => listTasks(filters), [key]);
  return { tasks: data, loading, error, refresh };
}

export function useNotifications(filters: NotificationFilters) {
  const key = JSON.stringify(filters);
  const { data, loading, error, refresh } = useAsyncData<NotificationListResult>(
    () => listNotifications(filters),
    [key],
  );
  return { notifications: data, loading, error, refresh };
}

/** PART 7 unified search with a 250 ms debounce (the useReport precedent). */
export function useProductivitySearch(filters: {
  q: string;
  date_from?: string;
  date_to?: string;
  priority?: string;
  category?: string;
  source?: string;
}) {
  const [state, setState] = useState<AsyncState<ProductivitySearchResult>>({
    data: null,
    loading: false,
    error: null,
  });
  const key = JSON.stringify(filters);

  useEffect(() => {
    const parsed = JSON.parse(key) as typeof filters;
    if (!parsed.q.trim() && !parsed.date_from && !parsed.source) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    setState((prev) => ({ ...prev, loading: true, error: null }));
    const handle = setTimeout(() => {
      searchProductivity(parsed)
        .then((data) => setState({ data, loading: false, error: null }))
        .catch((err: Error) => setState({ data: null, loading: false, error: err.message }));
    }, 250);
    return () => clearTimeout(handle);
  }, [key]);

  return { results: state.data, loading: state.loading, error: state.error };
}

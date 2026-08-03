/**
 * Typed API client for the Productivity Hub module.
 *
 * Mirrors `lib/api/reports.ts` / `lib/api/events.ts` one-to-one: thin
 * wrappers over the shared `api` client, same encoding contract (ids travel
 * decoded), server-side filter params. Updates go through PUT (the events
 * module precedent — the backend also accepts PATCH).
 */
import { api, type RequestOptions } from "@/lib/api/client";
import type {
  CalendarEntry,
  CalendarEntryListResult,
  CalendarFeed,
  NotificationListResult,
  ProductivityDashboard,
  ProductivityNotification,
  ProductivitySearchResult,
  ProductivityTask,
  RefreshNotificationsResult,
  RemindersFeed,
  TaskListResult,
} from "@/types";

// ------------------------------------------------------------ aggregation
export function getProductivityDashboard(options?: RequestOptions & { asOf?: string }): Promise<ProductivityDashboard> {
  const { asOf, ...rest } = options ?? {};
  return api.get<ProductivityDashboard>("/productivity/dashboard", {
    ...rest,
    query: asOf ? { as_of: asOf } : undefined,
  });
}

export function getCalendarFeed(
  dateFrom: string,
  dateTo: string,
  sources?: string[],
  options?: RequestOptions,
): Promise<CalendarFeed> {
  return api.get<CalendarFeed>("/productivity/calendar", {
    ...options,
    query: {
      date_from: dateFrom,
      date_to: dateTo,
      ...(sources && sources.length ? { sources: sources.join(",") } : {}),
    },
  });
}

export function getReminders(options?: RequestOptions): Promise<RemindersFeed> {
  return api.get<RemindersFeed>("/productivity/reminders", options);
}

export function searchProductivity(
  filters: {
    q?: string;
    date_from?: string;
    date_to?: string;
    priority?: string;
    category?: string;
    source?: string;
  },
  options?: RequestOptions,
): Promise<ProductivitySearchResult> {
  const query: Record<string, string> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value) query[key] = value;
  }
  return api.get<ProductivitySearchResult>("/productivity/search", { ...options, query });
}

// ------------------------------------------------------------------ tasks
export interface TaskFilters {
  q?: string;
  priority?: string;
  category?: string;
  completed?: boolean;
  pinned?: boolean;
  overdue?: boolean;
  due_from?: string;
  due_to?: string;
}

function cleanQuery(filters: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === "") continue;
    out[key] = typeof value === "boolean" ? String(value) : String(value);
  }
  return out;
}

export function listTasks(filters: TaskFilters = {}, options?: RequestOptions): Promise<TaskListResult> {
  return api.get<TaskListResult>("/productivity/tasks", {
    ...options,
    query: { page_size: "100", ...cleanQuery(filters as Record<string, unknown>) },
  });
}

export interface TaskPayload {
  title: string;
  description?: string;
  priority?: string;
  category?: string;
  start_date?: string;
  due_date?: string;
  completed?: boolean;
  pinned?: boolean;
  reminder?: string;
  tags?: string[];
  remarks?: string;
}

export function createTask(payload: TaskPayload, actor = "faculty:ui"): Promise<ProductivityTask> {
  return api.post<ProductivityTask>("/productivity/tasks", { ...payload, uploaded_by: actor });
}

export function updateTask(id: string, payload: Partial<TaskPayload>, actor = "faculty:ui"): Promise<ProductivityTask> {
  return api.put<ProductivityTask>(`/productivity/tasks/${id}`, { ...payload, uploaded_by: actor });
}

export function deleteTask(id: string): Promise<void> {
  return api.delete<void>(`/productivity/tasks/${id}`);
}

// ---------------------------------------------------------- calendar entries
export interface EntryPayload {
  title: string;
  start_date: string;
  description?: string;
  end_date?: string;
  start_time?: string;
  end_time?: string;
  location?: string;
  category?: string;
  tags?: string[];
}

export function listCalendarEntries(
  filters: { q?: string; category?: string; date_from?: string; date_to?: string } = {},
  options?: RequestOptions,
): Promise<CalendarEntryListResult> {
  return api.get<CalendarEntryListResult>("/productivity/calendar-entries", {
    ...options,
    query: { page_size: "100", ...cleanQuery(filters as Record<string, unknown>) },
  });
}

export function createCalendarEntry(payload: EntryPayload, actor = "faculty:ui"): Promise<CalendarEntry> {
  return api.post<CalendarEntry>("/productivity/calendar-entries", { ...payload, uploaded_by: actor });
}

export function updateCalendarEntry(id: string, payload: Partial<EntryPayload>, actor = "faculty:ui"): Promise<CalendarEntry> {
  return api.put<CalendarEntry>(`/productivity/calendar-entries/${id}`, { ...payload, uploaded_by: actor });
}

export function deleteCalendarEntry(id: string): Promise<void> {
  return api.delete<void>(`/productivity/calendar-entries/${id}`);
}

// ------------------------------------------------------------ notifications
export interface NotificationFilters {
  q?: string;
  state?: string;
  priority?: string;
  category?: string;
  source_module?: string;
}

export function listNotifications(
  filters: NotificationFilters = {},
  options?: RequestOptions,
): Promise<NotificationListResult> {
  return api.get<NotificationListResult>("/productivity/notifications", {
    ...options,
    query: { page_size: "100", ...cleanQuery(filters as Record<string, unknown>) },
  });
}

export function createNotification(
  payload: { title: string; body?: string; category?: string; priority?: string; link?: string },
  actor = "faculty:ui",
): Promise<ProductivityNotification> {
  return api.post<ProductivityNotification>("/productivity/notifications", { ...payload, uploaded_by: actor });
}

export interface NotificationPatch {
  is_read?: boolean;
  pinned?: boolean;
  archived?: boolean;
  snoozed_until?: string; // "" clears
}

export function updateNotification(
  id: string,
  patch: NotificationPatch,
  actor = "faculty:ui",
): Promise<ProductivityNotification> {
  return api.put<ProductivityNotification>(`/productivity/notifications/${id}`, {
    ...patch,
    uploaded_by: actor,
  });
}

export function deleteNotification(id: string): Promise<void> {
  return api.delete<void>(`/productivity/notifications/${id}`);
}

export function refreshNotifications(actor = "faculty:ui"): Promise<RefreshNotificationsResult> {
  return api.post<RefreshNotificationsResult>("/productivity/notifications/refresh", {
    uploaded_by: actor,
  });
}

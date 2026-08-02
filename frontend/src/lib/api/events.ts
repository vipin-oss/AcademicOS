/**
 * Events & Academic Activities API — frontend mirror of the `/events` contract.
 *
 * Mirrors `lib/api/finance.ts` one-to-one: every call reuses the shared
 * {@link api} wrapper (identical error normalisation, timeouts and aborts).
 * The backend exposes server-side PART 10 search/filters (`q`, `event_type`,
 * `year`, `role`, `department`, `organizer`, `status`).
 *
 * ENCODING CONTRACT (same as every module — do not break): ids travel
 * decoded (`obj:event:AB12…`); list Links encode exactly once and detail
 * pages decode exactly once. Never `encodeURIComponent` here.
 */
import { api } from "@/lib/api/client";
import type { RequestOptions } from "@/lib/api/client";
import { DEFAULT_EVENT_PAGE_SIZE } from "@/lib/events/constants";
import type {
  EventInputLinkGroup,
  EventMode,
  EventPriority,
  EventRegistration,
  EventResponse,
  EventsDashboard,
  EventStatus,
  EventType,
  ListEventsResponse,
  ParticipationRole,
  ParticipationRow,
  PresentationRow,
  ResearchObjectStatus,
  ScheduleRow,
  SpeakerRow,
} from "@/types";

export interface ListEventsParams {
  page?: number;
  pageSize?: number;
  /** Server-side token-AND search (title/code/organizer/venue/speakers). */
  q?: string;
  /** Event type (metadata vocabulary). */
  eventType?: EventType | null;
  /** Calendar year of the start date, e.g. "2026". */
  year?: string | null;
  /** Participation role (PART 2 vocabulary). */
  role?: ParticipationRole | null;
  department?: string | null;
  /** Organizer / co-organizer fragment. */
  organizer?: string | null;
  /** Event business status. */
  status?: EventStatus | null;
}

export interface CreateEventPayload {
  title: string;
  uploaded_by: string;
  status?: ResearchObjectStatus;
  event_code?: string | null;
  event_type?: EventType | null;
  organizer?: string | null;
  co_organizer?: string | null;
  venue?: string | null;
  mode?: EventMode | null;
  start_date?: string | null;
  end_date?: string | null;
  department?: string | null;
  school?: string | null;
  description?: string | null;
  objectives?: string | null;
  outcome?: string | null;
  event_status?: EventStatus | null;
  priority?: EventPriority | null;
  notes?: string | null;
  tags?: string[];
  participation?: ParticipationRow[];
  speakers?: SpeakerRow[];
  schedule?: ScheduleRow[];
  registration?: Partial<EventRegistration>;
  presentations?: PresentationRow[];
  links?: Partial<Record<EventInputLinkGroup, string[]>>;
}

/** Partial update: every present key replaces; absent keys are untouched. */
export type UpdateEventPayload = Partial<CreateEventPayload>;

function listEventsQuery(params: ListEventsParams): Record<string, string | number> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? DEFAULT_EVENT_PAGE_SIZE,
  };
  if (params.q?.trim()) query.q = params.q.trim();
  if (params.eventType) query.event_type = params.eventType;
  if (params.year?.trim()) query.year = params.year.trim();
  if (params.role) query.role = params.role;
  if (params.department?.trim()) query.department = params.department.trim();
  if (params.organizer?.trim()) query.organizer = params.organizer.trim();
  if (params.status) query.status = params.status;
  return query;
}

export function listEvents(
  params: ListEventsParams = {},
  options?: RequestOptions,
): Promise<ListEventsResponse> {
  return api.get<ListEventsResponse>("/events", {
    ...options,
    query: listEventsQuery(params),
  });
}

/** `id` must already be decoded (`obj:event:…`). */
export function getEvent(id: string, options?: RequestOptions): Promise<EventResponse> {
  return api.get<EventResponse>(`/events/${id}`, options);
}

export function createEvent(
  payload: CreateEventPayload,
  options?: RequestOptions,
): Promise<EventResponse> {
  return api.post<EventResponse>("/events", payload, options);
}

export function updateEvent(
  id: string,
  payload: UpdateEventPayload,
  options?: RequestOptions,
): Promise<EventResponse> {
  return api.put<EventResponse>(`/events/${id}`, payload, options);
}

export function deleteEvent(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/events/${id}`, options);
}

// ---------------------------------------------------------------------------
// Dashboard (PART 9)
// ---------------------------------------------------------------------------
export function getEventsDashboard(options?: RequestOptions): Promise<EventsDashboard> {
  return api.get<EventsDashboard>("/events/dashboard", options);
}

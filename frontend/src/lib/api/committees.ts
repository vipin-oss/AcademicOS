/**
 * Committees API — frontend mirror of the `/committees` contract.
 *
 * Mirrors `lib/api/research.ts` one-to-one: every call reuses the shared
 * {@link api} wrapper (identical error normalisation, timeouts and aborts).
 * The backend exposes server-side search + PART 9 filters (`q`,
 * `committee_type`, `department`, `chairperson`, `status`, `meeting_year`).
 *
 * ENCODING CONTRACT (same as every module — do not break): ids travel
 * decoded (`obj:committee:AB12…`); list Links encode exactly once and detail
 * pages decode exactly once. Never `encodeURIComponent` here.
 */
import { api } from "@/lib/api/client";
import type { RequestOptions } from "@/lib/api/client";
import { DEFAULT_COMMITTEE_PAGE_SIZE } from "@/lib/committees/constants";
import type {
  ActionItem,
  ActionPriority,
  ActionStatus,
  AgendaItem,
  AttendanceEntry,
  CommitteeLinkGroup,
  CommitteeMember,
  CommitteeResponse,
  CommitteesDashboard,
  ListCommitteesResponse,
  MeetingMode,
  MeetingResponse,
  ResearchObjectStatus,
} from "@/types";

// ---------------------------------------------------------------------------
// Committees (registry)
// ---------------------------------------------------------------------------
export interface ListCommitteesParams {
  page?: number;
  pageSize?: number;
  /** Server-side token-AND search (name/code/description/notes/member names). */
  q?: string;
  committeeType?: string | null;
  department?: string | null;
  /** Leadership-lens filter: committee chaired/convened/coordinated by … */
  chairperson?: string | null;
  status?: ResearchObjectStatus | null;
  /** Committees having at least one meeting in this calendar year. */
  meetingYear?: number | null;
}

/** One member row in the write payload (person id + role + tenure). */
export interface CommitteeMemberPayload {
  /** The faculty/student Object id (the backend's member-row key). */
  faculty_id: string;
  role: CommitteeMember["role"];
  start_date?: string | null;
  end_date?: string | null;
  remarks?: string | null;
}

export interface CreateCommitteePayload {
  name: string;
  uploaded_by: string;
  status?: ResearchObjectStatus;
  committee_code?: string | null;
  committee_type?: string | null;
  department?: string | null;
  school?: string | null;
  description?: string | null;
  constitution_date?: string | null;
  expiry_date?: string | null;
  notes?: string | null;
  tags?: string[];
  members?: CommitteeMemberPayload[];
  links?: Partial<Record<CommitteeLinkGroup, string[]>>;
}

/** Partial update: every present key replaces; absent keys are untouched. */
export type UpdateCommitteePayload = Partial<CreateCommitteePayload>;

function listCommitteesQuery(
  params: ListCommitteesParams,
): Record<string, string | number> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? DEFAULT_COMMITTEE_PAGE_SIZE,
  };
  if (params.q?.trim()) query.q = params.q.trim();
  if (params.committeeType?.trim()) query.committee_type = params.committeeType.trim();
  if (params.department?.trim()) query.department = params.department.trim();
  if (params.chairperson?.trim()) query.chairperson = params.chairperson.trim();
  if (params.status) query.status = params.status;
  if (params.meetingYear != null) query.meeting_year = params.meetingYear;
  return query;
}

export function listCommittees(
  params: ListCommitteesParams = {},
  options?: RequestOptions,
): Promise<ListCommitteesResponse> {
  return api.get<ListCommitteesResponse>("/committees", {
    ...options,
    query: listCommitteesQuery(params),
  });
}

/** `id` must already be decoded (`obj:committee:…`). */
export function getCommittee(id: string, options?: RequestOptions): Promise<CommitteeResponse> {
  return api.get<CommitteeResponse>(`/committees/${id}`, options);
}

export function createCommittee(
  payload: CreateCommitteePayload,
  options?: RequestOptions,
): Promise<CommitteeResponse> {
  return api.post<CommitteeResponse>("/committees", payload, options);
}

export function updateCommittee(
  id: string,
  payload: UpdateCommitteePayload,
  options?: RequestOptions,
): Promise<CommitteeResponse> {
  return api.put<CommitteeResponse>(`/committees/${id}`, payload, options);
}

export function deleteCommittee(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/committees/${id}`, options);
}

// ---------------------------------------------------------------------------
// Dashboard (PART 8)
// ---------------------------------------------------------------------------
export function getCommitteesDashboard(options?: RequestOptions): Promise<CommitteesDashboard> {
  return api.get<CommitteesDashboard>("/committees/dashboard", options);
}

// ---------------------------------------------------------------------------
// Meetings (PART 3)
// ---------------------------------------------------------------------------
export interface CreateMeetingPayload {
  title: string;
  uploaded_by: string;
  meeting_number?: string | null;
  meeting_date?: string | null;
  venue?: string | null;
  mode?: MeetingMode | null;
  agenda_items?: AgendaItem[];
  minutes?: string | null;
  attendance?: AttendanceEntry[];
  decisions?: string[];
  remarks?: string | null;
}

export type UpdateMeetingPayload = Partial<CreateMeetingPayload>;

export function addMeeting(
  committeeId: string,
  payload: CreateMeetingPayload,
  options?: RequestOptions,
): Promise<MeetingResponse> {
  return api.post<MeetingResponse>(`/committees/${committeeId}/meetings`, payload, options);
}

/** `id` must already be decoded (`obj:meeting:…`). */
export function getMeeting(id: string, options?: RequestOptions): Promise<MeetingResponse> {
  return api.get<MeetingResponse>(`/committees/meetings/${id}`, options);
}

export function updateMeeting(
  id: string,
  payload: UpdateMeetingPayload,
  options?: RequestOptions,
): Promise<MeetingResponse> {
  return api.put<MeetingResponse>(`/committees/meetings/${id}`, payload, options);
}

export function deleteMeeting(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/committees/meetings/${id}`, options);
}

// ---------------------------------------------------------------------------
// Action tracker (PART 5)
// ---------------------------------------------------------------------------
export interface CreateActionItemPayload {
  title: string;
  uploaded_by: string;
  assigned_to?: string | null;
  due_date?: string | null;
  priority?: ActionPriority | null;
  /** Action tracker state (wire key is `status` — mirrors the response). */
  status?: ActionStatus;
  progress?: number;
  completion_date?: string | null;
  remarks?: string | null;
}

export type UpdateActionItemPayload = Partial<CreateActionItemPayload>;

export function addActionItem(
  meetingId: string,
  payload: CreateActionItemPayload,
  options?: RequestOptions,
): Promise<ActionItem> {
  return api.post<ActionItem>(`/committees/meetings/${meetingId}/actions`, payload, options);
}

export function updateActionItem(
  id: string,
  payload: UpdateActionItemPayload,
  options?: RequestOptions,
): Promise<ActionItem> {
  return api.put<ActionItem>(`/committees/actions/${id}`, payload, options);
}

export function deleteActionItem(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/committees/actions/${id}`, options);
}

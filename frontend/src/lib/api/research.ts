/**
 * Research API — frontend mirror of the `/research` contract.
 *
 * Mirrors `lib/api/students.ts` one-to-one: every call reuses the shared
 * {@link api} wrapper (identical error normalisation, timeouts and aborts).
 * The backend exposes server-side search + PART 9 filters (`q`, `pi`,
 * `agency`, `status`, `year`, `department`, `object_id`); grant lenses use
 * `project_id` / `agency_id`.
 *
 * ENCODING CONTRACT (same as every module — do not break): ids travel
 * decoded (`obj:research_project:AB12…`); list Links encode exactly once and
 * detail pages decode exactly once. Never `encodeURIComponent` here.
 */
import { api } from "@/lib/api/client";
import type { RequestOptions } from "@/lib/api/client";
import {
  DEFAULT_AGENCY_PAGE_SIZE,
  DEFAULT_GRANT_PAGE_SIZE,
  DEFAULT_PROJECT_PAGE_SIZE,
} from "@/lib/research/constants";
import type {
  AgencyResponse,
  GrantExpenditure,
  GrantInstallment,
  GrantResponse,
  InstallmentStatus,
  ListAgenciesResponse,
  ListGrantsResponse,
  ListProjectsResponse,
  MilestoneStatus,
  ProjectLifecycleStatus,
  ProjectLinkGroup,
  ProjectMilestone,
  ProjectResponse,
  ProjectTeamGroup,
  ResearchDashboard,
  ResearchObjectStatus,
} from "@/types";

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------
export interface ListProjectsParams {
  page?: number;
  pageSize?: number;
  /** Server-side token-AND search (title/code/objectives/abstract/keywords). */
  q?: string;
  pi?: string | null;
  agency?: string | null;
  status?: ProjectLifecycleStatus | null;
  year?: number | null;
  department?: string | null;
  /** The object lens: "projects linked to Object X" (e.g. an agency's projects). */
  objectId?: string | null;
}

export interface CreateProjectPayload {
  title: string;
  uploaded_by: string;
  status?: ResearchObjectStatus;
  lifecycle_status?: ProjectLifecycleStatus;
  project_code?: string | null;
  department?: string | null;
  grant_number?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  duration?: string | null;
  budget_approved?: number | null;
  budget_utilized?: number | null;
  objectives?: string | null;
  keywords?: string[];
  abstract?: string | null;
  priority?: string | null;
  notes?: string | null;
  tags?: string[];
  links?: Partial<Record<ProjectLinkGroup, string[]>>;
  team?: Partial<Record<ProjectTeamGroup, string[]>>;
}

/** Partial update: every present key replaces; absent keys are untouched. */
export type UpdateProjectPayload = Partial<CreateProjectPayload>;

function listProjectsQuery(params: ListProjectsParams): Record<string, string | number> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? DEFAULT_PROJECT_PAGE_SIZE,
  };
  if (params.q?.trim()) query.q = params.q.trim();
  if (params.pi?.trim()) query.pi = params.pi.trim();
  if (params.agency?.trim()) query.agency = params.agency.trim();
  if (params.status) query.status = params.status;
  if (params.year != null) query.year = params.year;
  if (params.department?.trim()) query.department = params.department.trim();
  if (params.objectId) query.object_id = params.objectId;
  return query;
}

export function listProjects(
  params: ListProjectsParams = {},
  options?: RequestOptions,
): Promise<ListProjectsResponse> {
  return api.get<ListProjectsResponse>("/research/projects", {
    ...options,
    query: listProjectsQuery(params),
  });
}

export function listProjectsByObject(
  objectId: string,
  options?: RequestOptions,
): Promise<ListProjectsResponse> {
  return api.get<ListProjectsResponse>("/research/projects", {
    ...options,
    query: { object_id: objectId, page_size: 100 },
  });
}

/** `id` must already be decoded (`obj:research_project:…`). */
export function getProject(id: string, options?: RequestOptions): Promise<ProjectResponse> {
  return api.get<ProjectResponse>(`/research/projects/${id}`, options);
}

export function createProject(
  payload: CreateProjectPayload,
  options?: RequestOptions,
): Promise<ProjectResponse> {
  return api.post<ProjectResponse>("/research/projects", payload, options);
}

export function updateProject(
  id: string,
  payload: UpdateProjectPayload,
  options?: RequestOptions,
): Promise<ProjectResponse> {
  return api.put<ProjectResponse>(`/research/projects/${id}`, payload, options);
}

export function deleteProject(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/research/projects/${id}`, options);
}

// ---------------------------------------------------------------------------
// Project timeline (milestones + progress updates)
// ---------------------------------------------------------------------------
export interface MilestonePayload {
  title: string;
  date: string;
  status?: MilestoneStatus;
  notes?: string | null;
  uploaded_by?: string;
}

export function addMilestone(
  projectId: string,
  payload: MilestonePayload,
  options?: RequestOptions,
): Promise<ProjectMilestone> {
  return api.post<ProjectMilestone>(
    `/research/projects/${projectId}/milestones`,
    payload,
    options,
  );
}

export function updateMilestone(
  milestoneId: string,
  payload: Partial<MilestonePayload>,
  options?: RequestOptions,
): Promise<ProjectMilestone> {
  return api.put<ProjectMilestone>(`/research/milestones/${milestoneId}`, payload, options);
}

export function deleteMilestone(milestoneId: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/research/milestones/${milestoneId}`, options);
}

export interface ProgressUpdatePayload {
  date: string;
  percent: number;
  remark: string;
  uploaded_by?: string;
}

export function recordProgressUpdate(
  projectId: string,
  payload: ProgressUpdatePayload,
  options?: RequestOptions,
): Promise<ProjectResponse> {
  return api.post<ProjectResponse>(`/research/projects/${projectId}/updates`, payload, options);
}

// ---------------------------------------------------------------------------
// Grants
// ---------------------------------------------------------------------------
export interface ListGrantsParams {
  page?: number;
  pageSize?: number;
  q?: string;
  projectId?: string | null;
  agencyId?: string | null;
  status?: ResearchObjectStatus | null;
}

export interface CreateGrantPayload {
  title: string;
  grant_number: string;
  uploaded_by: string;
  status?: ResearchObjectStatus;
  amount?: number | null;
  release_schedule?: string | null;
  notes?: string | null;
  links?: Partial<Record<"projects" | "funding_agencies", string[]>>;
}

export type UpdateGrantPayload = Partial<CreateGrantPayload>;

export function listGrants(
  params: ListGrantsParams = {},
  options?: RequestOptions,
): Promise<ListGrantsResponse> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? DEFAULT_GRANT_PAGE_SIZE,
  };
  if (params.q?.trim()) query.q = params.q.trim();
  if (params.projectId) query.project_id = params.projectId;
  if (params.agencyId) query.agency_id = params.agencyId;
  if (params.status) query.status = params.status;
  return api.get<ListGrantsResponse>("/research/grants", { ...options, query });
}

/** `id` must already be decoded (`obj:grant:…`). */
export function getGrant(id: string, options?: RequestOptions): Promise<GrantResponse> {
  return api.get<GrantResponse>(`/research/grants/${id}`, options);
}

export function createGrant(
  payload: CreateGrantPayload,
  options?: RequestOptions,
): Promise<GrantResponse> {
  return api.post<GrantResponse>("/research/grants", payload, options);
}

export function updateGrant(
  id: string,
  payload: UpdateGrantPayload,
  options?: RequestOptions,
): Promise<GrantResponse> {
  return api.put<GrantResponse>(`/research/grants/${id}`, payload, options);
}

export function deleteGrant(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/research/grants/${id}`, options);
}

// ---------------------------------------------------------------------------
// Grant budget entries (installments + expenditure)
// ---------------------------------------------------------------------------
export interface InstallmentPayload {
  installment_no: number;
  date: string;
  amount: number;
  status?: InstallmentStatus;
  notes?: string | null;
  uploaded_by?: string;
}

export function addInstallment(
  grantId: string,
  payload: InstallmentPayload,
  options?: RequestOptions,
): Promise<GrantInstallment> {
  return api.post<GrantInstallment>(
    `/research/grants/${grantId}/installments`,
    payload,
    options,
  );
}

export function deleteInstallment(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/research/installments/${id}`, options);
}

export interface ExpenditurePayload {
  date: string;
  head: string;
  amount: number;
  reference?: string | null;
  notes?: string | null;
  uploaded_by?: string;
}

export function recordExpenditure(
  grantId: string,
  payload: ExpenditurePayload,
  options?: RequestOptions,
): Promise<GrantExpenditure> {
  return api.post<GrantExpenditure>(
    `/research/grants/${grantId}/expenditures`,
    payload,
    options,
  );
}

export function deleteExpenditure(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/research/expenditures/${id}`, options);
}

// ---------------------------------------------------------------------------
// Funding agencies
// ---------------------------------------------------------------------------
export interface ListAgenciesParams {
  page?: number;
  pageSize?: number;
  q?: string;
  status?: ResearchObjectStatus | null;
}

export interface CreateAgencyPayload {
  name: string;
  uploaded_by: string;
  status?: ResearchObjectStatus;
  website?: string | null;
  scheme?: string | null;
  contact_person?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  address?: string | null;
  notes?: string | null;
}

export type UpdateAgencyPayload = Partial<CreateAgencyPayload>;

export function listAgencies(
  params: ListAgenciesParams = {},
  options?: RequestOptions,
): Promise<ListAgenciesResponse> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? DEFAULT_AGENCY_PAGE_SIZE,
  };
  if (params.q?.trim()) query.q = params.q.trim();
  if (params.status) query.status = params.status;
  return api.get<ListAgenciesResponse>("/research/agencies", { ...options, query });
}

/** `id` must already be decoded (`obj:funding_agency:…`). */
export function getAgency(id: string, options?: RequestOptions): Promise<AgencyResponse> {
  return api.get<AgencyResponse>(`/research/agencies/${id}`, options);
}

export function createAgency(
  payload: CreateAgencyPayload,
  options?: RequestOptions,
): Promise<AgencyResponse> {
  return api.post<AgencyResponse>("/research/agencies", payload, options);
}

export function updateAgency(
  id: string,
  payload: UpdateAgencyPayload,
  options?: RequestOptions,
): Promise<AgencyResponse> {
  return api.put<AgencyResponse>(`/research/agencies/${id}`, payload, options);
}

export function deleteAgency(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/research/agencies/${id}`, options);
}

// ---------------------------------------------------------------------------
// Dashboard (PART 10)
// ---------------------------------------------------------------------------
export function getResearchDashboard(options?: RequestOptions): Promise<ResearchDashboard> {
  return api.get<ResearchDashboard>("/research/dashboard", options);
}

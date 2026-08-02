/**
 * Finance & Procurement API — frontend mirror of the `/finance` contract.
 *
 * Mirrors `lib/api/committees.ts` one-to-one: every call reuses the shared
 * {@link api} wrapper (identical error normalisation, timeouts and aborts).
 * The backend exposes server-side PART 12 search/filters (`q`, `vendor`,
 * `project`, `grant`, `status`, `department`, `financial_year`).
 *
 * ENCODING CONTRACT (same as every module — do not break): ids travel
 * decoded (`obj:purchase:AB12…`); list Links encode exactly once and detail
 * pages decode exactly once. Never `encodeURIComponent` here.
 */
import { api } from "@/lib/api/client";
import type { RequestOptions } from "@/lib/api/client";
import {
  DEFAULT_ASSET_PAGE_SIZE,
  DEFAULT_PROPOSAL_PAGE_SIZE,
  DEFAULT_VENDOR_PAGE_SIZE,
} from "@/lib/finance/constants";
import type {
  AssetCategory,
  AssetRegisterRow,
  AssetStatus,
  BudgetLine,
  FinanceDashboard,
  ListAssetRegisterResponse,
  ListBudgetsResponse,
  ListProposalsResponse,
  ListVendorsResponse,
  ProposalLinkGroup,
  ProposalPriority,
  ProposalResponse,
  ProposalStatus,
  QuotationRow,
  ComparativeRow,
  PurchaseOrderRow,
  BillRow,
  AssetRow,
  BankDetails,
  ResearchObjectStatus,
  VendorResponse,
} from "@/types";

// ---------------------------------------------------------------------------
// Purchase proposals (registry)
// ---------------------------------------------------------------------------
export interface ListProposalsParams {
  page?: number;
  pageSize?: number;
  /** Server-side token-AND search (number/title/purpose/vendor names). */
  q?: string;
  /** Vendor id or name fragment (section references). */
  vendor?: string | null;
  /** Linked project Object id. */
  project?: string | null;
  /** Linked grant Object id. */
  grant?: string | null;
  /** Proposal business status (metadata vocabulary). */
  status?: ProposalStatus | null;
  department?: string | null;
  /** Indian financial year "2026-27" (April-March). */
  financialYear?: string | null;
}

export interface CreateProposalPayload {
  title: string;
  uploaded_by: string;
  status?: ResearchObjectStatus;
  proposal_number?: string | null;
  department?: string | null;
  requested_by?: string | null;
  proposal_date?: string | null;
  purpose?: string | null;
  budget_head?: string | null;
  estimated_cost?: number | string | null;
  proposal_status?: ProposalStatus;
  priority?: ProposalPriority | null;
  notes?: string | null;
  tags?: string[];
  approval_meeting_id?: string | null;
  minutes?: string | null;
  recommendations?: string | null;
  quotations?: QuotationRow[];
  comparative?: ComparativeRow[];
  purchase_orders?: PurchaseOrderRow[];
  bills?: BillRow[];
  assets?: AssetRow[];
  links?: Partial<Record<ProposalLinkGroup, string[]>>;
}

/** Partial update: every present key replaces; absent keys are untouched. */
export type UpdateProposalPayload = Partial<CreateProposalPayload>;

function listProposalsQuery(
  params: ListProposalsParams,
): Record<string, string | number> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? DEFAULT_PROPOSAL_PAGE_SIZE,
  };
  if (params.q?.trim()) query.q = params.q.trim();
  if (params.vendor?.trim()) query.vendor = params.vendor.trim();
  if (params.project?.trim()) query.project = params.project.trim();
  if (params.grant?.trim()) query.grant = params.grant.trim();
  if (params.status) query.status = params.status;
  if (params.department?.trim()) query.department = params.department.trim();
  if (params.financialYear?.trim()) query.financial_year = params.financialYear.trim();
  return query;
}

export function listProposals(
  params: ListProposalsParams = {},
  options?: RequestOptions,
): Promise<ListProposalsResponse> {
  return api.get<ListProposalsResponse>("/finance/proposals", {
    ...options,
    query: listProposalsQuery(params),
  });
}

/** `id` must already be decoded (`obj:purchase:…`). */
export function getProposal(id: string, options?: RequestOptions): Promise<ProposalResponse> {
  return api.get<ProposalResponse>(`/finance/proposals/${id}`, options);
}

export function createProposal(
  payload: CreateProposalPayload,
  options?: RequestOptions,
): Promise<ProposalResponse> {
  return api.post<ProposalResponse>("/finance/proposals", payload, options);
}

export function updateProposal(
  id: string,
  payload: UpdateProposalPayload,
  options?: RequestOptions,
): Promise<ProposalResponse> {
  return api.put<ProposalResponse>(`/finance/proposals/${id}`, payload, options);
}

export function deleteProposal(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/finance/proposals/${id}`, options);
}

// ---------------------------------------------------------------------------
// Vendor registry (PART 3)
// ---------------------------------------------------------------------------
export interface ListVendorsParams {
  page?: number;
  pageSize?: number;
  /** Server-side token-AND search (name/GST/PAN/contact). */
  q?: string;
}

export interface CreateVendorPayload {
  name: string;
  uploaded_by: string;
  status?: ResearchObjectStatus;
  gst_number?: string | null;
  pan?: string | null;
  contact_person?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  bank_details?: BankDetails;
  notes?: string | null;
  tags?: string[];
}

/** Partial update: every present key replaces; absent keys are untouched. */
export type UpdateVendorPayload = Partial<CreateVendorPayload>;

export function listVendors(
  params: ListVendorsParams = {},
  options?: RequestOptions,
): Promise<ListVendorsResponse> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? DEFAULT_VENDOR_PAGE_SIZE,
  };
  if (params.q?.trim()) query.q = params.q.trim();
  return api.get<ListVendorsResponse>("/finance/vendors", { ...options, query });
}

export function getVendor(id: string, options?: RequestOptions): Promise<VendorResponse> {
  return api.get<VendorResponse>(`/finance/vendors/${id}`, options);
}

export function createVendor(
  payload: CreateVendorPayload,
  options?: RequestOptions,
): Promise<VendorResponse> {
  return api.post<VendorResponse>("/finance/vendors", payload, options);
}

export function updateVendor(
  id: string,
  payload: UpdateVendorPayload,
  options?: RequestOptions,
): Promise<VendorResponse> {
  return api.put<VendorResponse>(`/finance/vendors/${id}`, payload, options);
}

export function deleteVendor(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/finance/vendors/${id}`, options);
}

// ---------------------------------------------------------------------------
// Dashboard (PART 11) + budget lens (PART 9) + asset register (PART 8)
// ---------------------------------------------------------------------------
export function getFinanceDashboard(options?: RequestOptions): Promise<FinanceDashboard> {
  return api.get<FinanceDashboard>("/finance/dashboard", options);
}

export function listBudgetLines(options?: RequestOptions): Promise<ListBudgetsResponse> {
  return api.get<ListBudgetsResponse>("/finance/budgets", options);
}

export interface ListAssetRegisterParams {
  page?: number;
  pageSize?: number;
  q?: string;
  category?: AssetCategory | null;
  status?: AssetStatus | null;
}

export function listAssetRegister(
  params: ListAssetRegisterParams = {},
  options?: RequestOptions,
): Promise<ListAssetRegisterResponse> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? DEFAULT_ASSET_PAGE_SIZE,
  };
  if (params.q?.trim()) query.q = params.q.trim();
  if (params.category) query.category = params.category;
  if (params.status) query.status = params.status;
  return api.get<ListAssetRegisterResponse>("/finance/assets", { ...options, query });
}

export type { AssetRegisterRow };

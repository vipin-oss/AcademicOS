/**
 * Typed API client for the Reports & Analytics module.
 *
 * Mirrors `lib/api/events.ts` one-to-one: thin wrappers over the shared
 * `api` client, same encoding contract (ids travel decoded), server-side
 * PART 12 filter params. The module is read-only — GETs only. Exports are
 * plain GET downloads (`exportUrl` builds the query string for an <a href>).
 */
import { api, type RequestOptions } from "@/lib/api/client";
import { API_BASE_URL } from "@/config/env";
import type {
  ReportFilters,
  ReportView,
  ReportsCatalogue,
  ReportsDashboard,
} from "@/types";
import { cleanFilters } from "@/lib/reports/constants";

export function getReportsCatalogue(options?: RequestOptions): Promise<ReportsCatalogue> {
  return api.get<ReportsCatalogue>("/reports", options);
}

export function getReportsDashboard(options?: RequestOptions): Promise<ReportsDashboard> {
  return api.get<ReportsDashboard>("/reports/dashboard", options);
}

export function getReport(
  kind: string,
  filters: ReportFilters = {},
  options?: RequestOptions,
): Promise<ReportView> {
  return api.get<ReportView>(`/reports/${kind}`, {
    ...options,
    query: cleanFilters(filters),
  });
}

/** PART 11 export URL — plain link download (GET, no auth header needed). */
export function exportUrl(kind: string, format: string, filters: ReportFilters = {}): string {
  const params = new URLSearchParams({ kind, format, ...cleanFilters(filters) });
  return `${API_BASE_URL}/reports/export?${params.toString()}`;
}

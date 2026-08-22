/**
 * Search API (Sprint-5 M2). Mirrors `lib/api/objects.ts`: every call reuses
 * the shared client (bearer token attached automatically).
 */

import { api, type RequestOptions } from "@/lib/api/client";

/** Provenance of a search hit: which index leg produced it. */
export type SearchIndexSource = "lexical" | "semantic" | "both";

export interface SearchHit {
  object_id: string;
  object_type: string;
  title: string;
  version: number;
  index_source: SearchIndexSource;
  score: number;
}

export interface SearchResponse {
  results: SearchHit[];
}

export interface SearchParams {
  text?: string;
  object_type?: string;
  title?: string;
  date_from?: string;
  date_to?: string;
  year?: string;
  limit?: number;
}

export function searchObjects(
  params: SearchParams,
  options?: RequestOptions,
): Promise<SearchResponse> {
  return api.get<SearchResponse>("/search", {
    ...options,
    query: {
      ...(params.text ? { text: params.text } : {}),
      ...(params.object_type ? { object_type: params.object_type } : {}),
      ...(params.title ? { title: params.title } : {}),
      ...(params.date_from ? { date_from: params.date_from } : {}),
      ...(params.date_to ? { date_to: params.date_to } : {}),
      ...(params.year ? { year: params.year } : {}),
      ...(params.limit !== undefined ? { limit: String(params.limit) } : {}),
    },
  });
}

export function syncSearchIndex(options?: RequestOptions): Promise<{ applied: number }> {
  return api.post<{ applied: number }>("/search/index/sync", undefined, options);
}

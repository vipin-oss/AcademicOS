import { api, type RequestOptions } from "@/lib/api/client";
import { DEFAULT_PAGE_SIZE } from "@/lib/objects/constants";
import type {
  ListObjectsResponse,
  MetadataFieldPayload,
  ObjectResponse,
  ObjectStatus,
} from "@/types";

/**
 * Objects API.
 *
 * ENCODING CONTRACT (do not break — it caused the `obj%3Acourse%3A…` bug):
 *   1. the list Link encodes the id EXACTLY ONCE  -> `/objects/${encodeURIComponent(id)}`
 *   2. the detail page decodes `params.id` EXACTLY ONCE -> `decodeURIComponent(params.id)`
 *   3. this layer sends the decoded id verbatim   -> `/objects/${id}`
 * Colons are legal path characters, so `obj:course:AB12` travels as-is and
 * `ObjectId.parse` on the backend accepts it.
 */

export interface CreateObjectPayload {
  object_type: string;
  title: string;
  created_by: string;
  status?: ObjectStatus;
  object_id?: string;
  metadata?: MetadataFieldPayload[];
}

/**
 * PUT body accepted by the backend (`UpdateObjectRequest`).
 * The aggregate is intentionally narrow: only status + metadata are mutable.
 */
export interface UpdateObjectPayload {
  updated_by: string;
  status?: ObjectStatus;
  metadata?: MetadataFieldPayload[];
}

export interface ListObjectsParams {
  page?: number;
  pageSize?: number;
}

export function listObjects(
  params: ListObjectsParams = {},
  options?: RequestOptions,
): Promise<ListObjectsResponse> {
  const { page = 1, pageSize = DEFAULT_PAGE_SIZE } = params;
  return api.get<ListObjectsResponse>("/objects", {
    ...options,
    query: { page, page_size: pageSize },
  });
}

/** `id` must already be decoded (`obj:course:…`) — never encode it here. */
export function getObject(id: string, options?: RequestOptions): Promise<ObjectResponse> {
  return api.get<ObjectResponse>(`/objects/${id}`, options);
}

export function createObject(
  payload: CreateObjectPayload,
  options?: RequestOptions,
): Promise<ObjectResponse> {
  return api.post<ObjectResponse>("/objects", payload, options);
}

/** `id` must already be decoded (`obj:course:…`) — never encode it here. */
export function updateObject(
  id: string,
  payload: UpdateObjectPayload,
  options?: RequestOptions,
): Promise<ObjectResponse> {
  return api.put<ObjectResponse>(`/objects/${id}`, payload, options);
}

/** `id` must already be decoded (`obj:course:…`) — never encode it here. */
export function deleteObject(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/objects/${id}`, options);
}

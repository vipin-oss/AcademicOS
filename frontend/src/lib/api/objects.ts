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
  /** Comma-separated object types to filter (e.g. "event,publication,grant") */
  objectType?: string;
}

export function listObjects(
  params: ListObjectsParams = {},
  options?: RequestOptions,
): Promise<ListObjectsResponse> {
  const { page = 1, pageSize = DEFAULT_PAGE_SIZE, objectType } = params;
  const query: Record<string, string | number> = { page, page_size: pageSize };
  if (objectType) {
    query.object_type = objectType;
  }
  return api.get<ListObjectsResponse>("/objects", {
    ...options,
    query,
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

// ---------------------------------------------------------------------------
// Knowledge graph + ACL (final release — previously unwired backend routes)
// ---------------------------------------------------------------------------

/** `GET /objects/{id}/graph` — the object's typed outgoing edges. */
export interface GraphItem {
  id: string;
  object_type: string;
  title: string;
  kind: string;
  direction: string;
}

export interface GraphResponse {
  items: GraphItem[];
  total_count: number;
  has_cycle: boolean;
  cycle_nodes: string[];
  truncated: boolean;
}

export function getObjectGraph(
  id: string,
  options?: RequestOptions,
): Promise<GraphResponse> {
  return api.get<GraphResponse>(`/objects/${id}/graph`, options);
}

/** `GET /objects/{id}/graph/path` — shortest path between two objects. */
export function getGraphPath(
  fromId: string,
  toId: string,
  options?: RequestOptions,
): Promise<{ items: GraphItem[]; found: boolean }> {
  return api.get<{ items: GraphItem[]; found: boolean }>(
    `/objects/${fromId}/graph/path?target=${encodeURIComponent(toId)}`,
    options,
  );
}

/** `GET /objects/{id}/acl` — the object's permission metadata. */
export interface AclResponse {
  owner: string;
  readers: string[];
  writers: string[];
  managers: string[];
}

export function getObjectAcl(id: string, options?: RequestOptions): Promise<AclResponse> {
  return api.get<AclResponse>(`/objects/${id}/acl`, options);
}

/** `PUT /objects/{id}/acl` — replace the permission metadata. */
export function updateObjectAcl(
  id: string,
  acl: { readers?: string[]; writers?: string[]; managers?: string[] },
  options?: RequestOptions,
): Promise<AclResponse> {
  return api.put<AclResponse>(`/objects/${id}/acl`, acl, options);
}

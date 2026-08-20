/**
 * Document Folders API — organize documents into folders.
 *
 * Folders are UniversalObjects with type=FOLDER. Document-folder membership
 * uses CONTAINS relationships. Tags and favorites use document metadata.
 */
import { api, type RequestOptions } from "@/lib/api/client";

export interface Folder {
  id: string;
  name: string;
  parent_id: string | null;
  document_count: number;
  created_by: string;
  created_at: string;
}

export interface FolderListResponse {
  items: Folder[];
  total: number;
}

export function listFolders(
  params: { parentId?: string | null } = {},
  options?: RequestOptions,
): Promise<FolderListResponse> {
  const query: Record<string, string> = {};
  if (params.parentId) query.parent_id = params.parentId;
  return api.get<FolderListResponse>("/documents/folders", { ...options, query });
}

export function listAllFolders(options?: RequestOptions): Promise<FolderListResponse> {
  return api.get<FolderListResponse>("/documents/folders/all", options);
}

export function createFolder(
  name: string,
  parentId?: string | null,
): Promise<Folder> {
  return api.post<Folder>("/documents/folders", { name, parent_id: parentId ?? null });
}

export function renameFolder(id: string, name: string): Promise<Folder> {
  return api.put<Folder>(`/documents/folders/${id}`, { name });
}

export function deleteFolder(id: string): Promise<void> {
  return api.delete(`/documents/folders/${id}`);
}

export function moveFolder(id: string, newParentId: string | null): Promise<Folder> {
  return api.put<Folder>(`/documents/folders/${id}/move`, { new_parent_id: newParentId });
}

export function addDocumentToFolder(folderId: string, documentId: string): Promise<{ status: string }> {
  return api.post(`/documents/folders/${folderId}/documents/${documentId}`, {});
}

export function removeDocumentFromFolder(folderId: string, documentId: string): Promise<void> {
  return api.delete(`/documents/folders/${folderId}/documents/${documentId}`);
}

export function listDocumentsInFolder(
  folderId: string,
  params: { page?: number; pageSize?: number } = {},
): Promise<{ items: Array<{ id: string; title: string; object_type: string; status: string }>; total: number }> {
  return api.get(`/documents/folders/${folderId}/documents`, {
    query: { page: params.page ?? 1, page_size: params.pageSize ?? 20 },
  });
}

export function setDocumentTags(documentId: string, tags: string[]): Promise<{ tags: string[] }> {
  return api.put(`/documents/folders/tags/${documentId}`, { tags });
}

export function toggleFavorite(documentId: string, favorite: boolean): Promise<{ favorite: boolean }> {
  return api.put(`/documents/folders/favorite/${documentId}`, { favorite });
}

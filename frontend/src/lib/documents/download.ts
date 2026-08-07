/**
 * Authenticated document download (Sprint M10, final polish).
 * The download endpoints require the bearer token, so plain <a href>
 * links fail; this helper fetches the bytes with the API client and
 * triggers a browser download via an object URL.
 */
import { api } from "@/lib/api/client";
import type { DocumentResponse } from "@/types";

export async function downloadDocument(doc: DocumentResponse): Promise<void> {
  const blob = await api.getBlob(`/documents/${doc.id}/download`);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = doc.file_name || doc.title || "document";
  window.document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

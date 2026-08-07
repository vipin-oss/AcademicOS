/**
 * Authenticated document download (Sprint M10, final polish).
 * The download endpoints require the bearer token, so plain <a href>
 * links fail; this helper fetches the bytes with the API client and
 * triggers a browser download via an object URL.
 */
import { api } from "@/lib/api/client";

/** What the downloader needs: the id plus optional names for the filename. */
export interface DownloadableDocument {
  id: string;
  file_name?: string;
  title?: string;
}

export async function downloadDocument(doc: DownloadableDocument): Promise<void> {
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

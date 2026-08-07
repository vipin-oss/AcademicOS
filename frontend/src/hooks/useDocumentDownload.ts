"use client";

/**
 * Authenticated document download with busy/error state (M10 RC1).
 *
 * The download endpoints require the bearer token, so plain `<a href>`
 * links 401 in the browser. This hook wraps {@link downloadDocument} and
 * exposes the in-flight id plus a human-readable error so every call site
 * (row, card, preview, detail page) renders the same honest UX.
 */
import { useCallback, useState } from "react";
import { downloadDocument } from "@/lib/documents/download";
import { toErrorMessage } from "@/lib/api/client";
import type { DocumentResponse } from "@/types";

export function useDocumentDownload() {
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const download = useCallback(async (doc: DocumentResponse) => {
    setError(null);
    setDownloadingId(doc.id);
    try {
      await downloadDocument(doc);
    } catch (err) {
      setError(toErrorMessage(err, "The document could not be downloaded."));
    } finally {
      setDownloadingId(null);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { download, downloadingId, error, clearError };
}

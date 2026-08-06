import { useEffect, useState } from "react";
import { Download, Eye, FileWarning } from "lucide-react";
import type { DocumentResponse } from "@/types";
import { FileIcon } from "./FileIcon";
import { formatFileSize } from "@/lib/documents/constants";
import { api, toErrorMessage } from "@/lib/api/client";

/**
 * Inline preview pane (Sprint-3 M3). PDF documents are fetched with the
 * authenticated API client (an iframe cannot send the Authorization
 * header) and rendered inline via an object URL; the paired Download
 * link uses the same authorized blob. Non-PDF types keep the honest
 * placeholder plus the download action.
 */
export function DocumentPreview({ document }: { document: DocumentResponse }) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const canPreview = document.document_type === "pdf" && Boolean(document.url);

  useEffect(() => {
    if (!canPreview) return;
    const controller = new AbortController();
    let objectUrl: string | null = null;

    api
      .getBlob(`/documents/${document.id}/download`, { signal: controller.signal })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
        setPreviewError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === "AbortError") return;
        setPreviewError(toErrorMessage(err, "The document could not be loaded for preview."));
      });

    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [document.id, document.url, canPreview]);

  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface-2)] px-6 py-10 text-center">
      {previewUrl ? (
        <iframe
          src={previewUrl}
          title={`Preview of ${document.file_name || document.title}`}
          className="h-[70vh] w-full rounded-lg border border-[var(--border-subtle)] bg-white"
        />
      ) : (
        <>
          <FileIcon type={document.document_type} className="h-14 w-14" />
          <div>
            <p className="font-medium text-[var(--text-primary)]">{document.file_name || document.title}</p>
            <p className="text-xs text-[var(--text-tertiary)]">
              {formatFileSize(document.file_size)} · {document.mime_type || document.document_type}
            </p>
          </div>
          <div className="flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
            {previewError ? (
              <>
                <FileWarning className="h-4 w-4" aria-hidden="true" />
                {previewError}
              </>
            ) : (
              <>
                <Eye className="h-4 w-4" aria-hidden="true" />
                {canPreview
                  ? "Loading preview…"
                  : "Preview is available for PDF documents."}
              </>
            )}
          </div>
        </>
      )}
      {document.url ? (
        <a
          href={previewUrl ?? document.url}
          download={document.file_name || document.title}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
        >
          <Download className="h-4 w-4" aria-hidden="true" /> Download
        </a>
      ) : (
        <button
          type="button"
          disabled
          className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-tertiary)] opacity-50"
        >
          <Download className="h-4 w-4" aria-hidden="true" /> Download unavailable
        </button>
      )}
    </div>
  );
}

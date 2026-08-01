import { Download, Eye } from "lucide-react";
import type { DocumentResponse } from "@/types";
import { FileIcon } from "./FileIcon";
import { formatFileSize } from "@/lib/documents/constants";

/**
 * Inline preview pane. Full document preview (PDF/image rendition, etc.)
 * requires a backend preview endpoint, so until then this shows an honest
 * placeholder plus a working download when a file URL is available.
 */
export function DocumentPreview({ document }: { document: DocumentResponse }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface-2)] px-6 py-10 text-center">
      <FileIcon type={document.document_type} className="h-14 w-14" />
      <div>
        <p className="font-medium text-[var(--text-primary)]">{document.file_name || document.title}</p>
        <p className="text-xs text-[var(--text-tertiary)]">
          {formatFileSize(document.file_size)} · {document.mime_type || document.document_type}
        </p>
      </div>
      <div className="flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
        <Eye className="h-4 w-4" aria-hidden="true" />
        Preview is not available yet — the backend preview endpoint has not shipped.
      </div>
      {document.url ? (
        <a
          href={document.url}
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

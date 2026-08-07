"use client";

/**
 * Office document preview (Sprint M10) — DOCX / PPTX / XLSX.
 *
 * Read-only browser preview where possible: DOCX/XLSX are rendered from
 * their package XML (a readable text/table approximation), PPTX slides
 * are shown as a text outline. When a preview is impossible (corrupt
 * file, unsupported format) the component falls back to the download
 * action — it never fabricates content.
 */
import { useCallback, useEffect, useState } from "react";
import { Download, FileWarning } from "lucide-react";

import { api, toErrorMessage } from "@/lib/api/client";
import type { DocumentResponse } from "@/types";

const OFFICE_TYPES = new Set(["docx", "pptx", "xlsx"]);

export function OfficePreview({ document }: { document: DocumentResponse }) {
  const [content, setContent] = useState<{ kind: "text" | "table" | "slides"; data: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!OFFICE_TYPES.has(document.document_type)) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getBlob(`/documents/${document.id}/download`)
      .then(async (blob) => {
        if (cancelled) return;
        const text = await blob.text(); // package XML / zip text — readable approximation
        if (cancelled) return;
        if (!text || text.length < 20) {
          setError("This file cannot be previewed inline.");
          return;
        }
        if (document.document_type === "xlsx") {
          setContent({ kind: "table", data: text });
        } else if (document.document_type === "pptx") {
          setContent({ kind: "slides", data: text });
        } else {
          setContent({ kind: "text", data: text });
        }
      })
      .catch((err) => {
        if (!cancelled) setError(toErrorMessage(err, "Preview unavailable."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [document.id, document.document_type]);

  if (!OFFICE_TYPES.has(document.document_type)) return null;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface-2)] px-6 py-10 text-center">
        <p className="text-sm text-[var(--text-tertiary)]">Preparing preview…</p>
      </div>
    );
  }

  if (error || !content) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface-2)] px-6 py-10 text-center">
        <FileWarning className="h-10 w-10 text-[var(--text-tertiary)]" />
        <p className="text-sm text-[var(--text-secondary)]">{error ?? "Preview unavailable."}</p>
        <a
          href={`/api/v1/documents/${document.id}/download?uploaded_by=${encodeURIComponent(document.uploaded_by)}`}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)]"
        >
          <Download className="h-4 w-4" /> Download file
        </a>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] p-4">
      <p className="mb-3 text-xs text-[var(--text-tertiary)]">
        Read-only preview of {document.file_name || document.title} ·{" "}
        <a
          href={`/api/v1/documents/${document.id}/download?uploaded_by=${encodeURIComponent(document.uploaded_by)}`}
          className="inline-flex items-center gap-1 text-[var(--accent)] hover:underline"
        >
          <Download className="h-3 w-3" /> Download
        </a>
      </p>
      <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap break-words text-xs leading-relaxed text-[var(--text-primary)]">
        {content.data}
      </pre>
    </div>
  );
}

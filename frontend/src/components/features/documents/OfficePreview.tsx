"use client";

/**
 * Office document preview (Sprint M10, final polish).
 *
 * DOCX / PPTX / XLSX read-only browser preview: the package XML is
 * parsed with JSZip into a readable text/table/slides approximation.
 * When a preview is impossible (corrupt file, unsupported structure) the
 * component falls back to the authenticated download action — it never
 * fabricates content and never uses an unauthenticated link.
 */
import { useCallback, useEffect, useState } from "react";
import { Download, FileWarning } from "lucide-react";

import { api, toErrorMessage } from "@/lib/api/client";
import { downloadDocument } from "@/lib/documents/download";
import { extractOfficeText } from "@/lib/documents/officeText";
import type { DocumentResponse } from "@/types";

const OFFICE_TYPES = new Set(["docx", "pptx", "xlsx"]);

export function OfficePreview({ document }: { document: DocumentResponse }) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!OFFICE_TYPES.has(document.document_type)) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getBlob(`/documents/${document.id}/download`)
      .then(async (blob) => {
        const text = await extractOfficeText(
          blob,
          document.document_type as "docx" | "pptx" | "xlsx",
        );
        if (cancelled) return;
        if (!text || text.length < 5) {
          setError("This file cannot be previewed inline.");
          return;
        }
        setContent(text);
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

  const download = useCallback(async () => {
    setDownloading(true);
    try {
      await downloadDocument(document);
    } catch (err) {
      setError(toErrorMessage(err, "Download failed."));
    } finally {
      setDownloading(false);
    }
  }, [document]);

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
        <button
          type="button"
          onClick={() => void download()}
          disabled={downloading}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:opacity-60"
        >
          <Download className="h-4 w-4" /> {downloading ? "Downloading…" : "Download file"}
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] p-4">
      <p className="mb-3 text-xs text-[var(--text-tertiary)]">
        Read-only preview of {document.file_name || document.title} ·{" "}
        <button
          type="button"
          onClick={() => void download()}
          disabled={downloading}
          className="inline-flex items-center gap-1 text-[var(--accent)] hover:underline disabled:opacity-60"
        >
          <Download className="h-3 w-3" /> Download
        </button>
      </p>
      <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap break-words text-xs leading-relaxed text-[var(--text-primary)]">
        {content}
      </pre>
    </div>
  );
}

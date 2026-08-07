"use client";

/**
 * Citation workspace (Sprint M10).
 *
 * Copies the document citation (academic formatting), a page reference
 * (e.g. "p. 3"), or a paragraph reference (page + selected text
 * excerpt) to the clipboard. Page references are persistent: they stay
 * valid as long as the document exists and are formatted from the
 * current page / selection.
 */
import { useCallback, useState } from "react";
import { BookOpen, Check, Copy } from "lucide-react";

import type { DocumentResponse } from "@/types";

export interface CitationPanelProps {
  document: DocumentResponse;
  currentPage: number;
  /** The current text selection inside the extracted-text panel. */
  selection: string;
}

/** Academic citation formatting (MLA-style): Title. Type. Institution, Year. */
export function formatCitation(document: DocumentResponse): string {
  const title = document.title || document.file_name || "Untitled";
  const type = (document.document_type || "document").toUpperCase();
  const year = document.created_at ? new Date(document.created_at).getFullYear() : undefined;
  return `${title}. ${type}${year ? `, ${year}` : ""}. AcademicOS.`;
}

export function formatPageReference(page: number): string {
  return `p. ${page}`;
}

export function formatParagraphReference(page: number, excerpt: string): string {
  const snippet = excerpt.trim().replace(/\s+/g, " ").slice(0, 120);
  return snippet ? `p. ${page}, "${snippet}…"` : `p. ${page}`;
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export function CitationPanel({ document, currentPage, selection }: CitationPanelProps) {
  const [copied, setCopied] = useState<string | null>(null);

  const copy = useCallback(async (key: string, text: string) => {
    const ok = await copyText(text);
    if (ok) {
      setCopied(key);
      window.setTimeout(() => setCopied(null), 1500);
    }
  }, []);

  const citation = formatCitation(document);
  const pageRef = formatPageReference(currentPage);
  const paragraphRef = formatParagraphReference(currentPage, selection);

  const rows: { key: string; label: string; value: string }[] = [
    { key: "citation", label: "Copy citation", value: citation },
    { key: "page", label: "Copy page reference", value: pageRef },
    { key: "paragraph", label: "Copy paragraph reference", value: paragraphRef },
  ];

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
        <BookOpen className="h-4 w-4 text-[var(--accent)]" /> Citation
      </h3>
      <div className="space-y-2">
        {rows.map((row) => (
          <button
            key={row.key}
            type="button"
            onClick={() => void copy(row.key, row.value)}
            className="flex w-full items-start justify-between gap-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-3 py-2 text-left text-xs hover:bg-[var(--bg-hover)]"
          >
            <span className="min-w-0">
              <span className="block font-medium text-[var(--text-secondary)]">{row.label}</span>
              <span className="block break-words text-[var(--text-primary)]">{row.value}</span>
            </span>
            {copied === row.key ? (
              <Check className="h-4 w-4 shrink-0 text-[var(--success)]" />
            ) : (
              <Copy className="h-4 w-4 shrink-0 text-[var(--text-tertiary)]" />
            )}
          </button>
        ))}
      </div>
      {selection && (
        <p className="mt-2 text-[10px] text-[var(--text-tertiary)]">
          Paragraph reference uses the current selection.
        </p>
      )}
    </div>
  );
}

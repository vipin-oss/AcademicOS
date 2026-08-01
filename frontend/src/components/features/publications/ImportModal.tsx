"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { FileUp, Link2, X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { importPublications } from "@/lib/api/publications";
import { BIBLIOGRAPHY_FORMATS } from "@/lib/publications/constants";
import { useModalDismiss } from "@/hooks/useModalDismiss";
import { cn } from "@/lib/utils";
import type { BibliographyFormat, PublicationImportResult } from "@/types";
import { Spinner } from "@/components/features/objects/Spinner";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none disabled:cursor-not-allowed disabled:opacity-60";

/**
 * Bulk import (FR-PUB-003): paste BibTeX / RIS / CSV (or load it from a file)
 * and get back the exact duplicate/error report — nothing is silently
 * swallowed, duplicates list the existing record they matched.
 */
export function ImportModal({
  open,
  onClose,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  onImported: (result: PublicationImportResult) => void;
}) {
  const [fmt, setFmt] = useState<BibliographyFormat>("bibtex");
  const [text, setText] = useState("");
  const [uploadedBy, setUploadedBy] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<PublicationImportResult | null>(null);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useModalDismiss({ open, onDismiss: onClose, disabled: submitting });

  useEffect(() => {
    if (!open) return;
    setFmt("bibtex");
    setText("");
    setFormError(null);
    setSubmitting(false);
    setResult(null);
    submittingRef.current = false;
    if (fileRef.current) fileRef.current.value = "";
  }, [open]);

  useEffect(() => {
    if (open) firstFieldRef.current?.focus();
  }, [open]);

  if (!open) return null;

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    try {
      setText(await file.text());
      const lower = file.name.toLowerCase();
      if (lower.endsWith(".bib")) setFmt("bibtex");
      else if (lower.endsWith(".ris")) setFmt("ris");
      else if (lower.endsWith(".csv")) setFmt("csv");
    } catch {
      setFormError("Could not read that file.");
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;
    if (!text.trim()) {
      setFormError("Paste (or load) the bibliography to import.");
      return;
    }
    if (!uploadedBy.trim()) {
      setFormError("“Added by” is required — your identity goes on the imported records.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);
    setFormError(null);
    setResult(null);
    try {
      const report = await importPublications({
        fmt,
        text,
        uploaded_by: uploadedBy.trim(),
      });
      setResult(report);
      onImported(report);
    } catch (error) {
      setFormError(toErrorMessage(error, "The import failed."));
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !submitting) onClose();
      }}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 id="import-modal-title" className="text-base font-semibold text-[var(--text-primary)]">
            Import References
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close dialog"
            className="rounded-lg p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:opacity-50"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {formError ? (
            <p
              role="alert"
              className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
            >
              {formError}
            </p>
          ) : null}

          {!result ? (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr]">
                <div>
                  <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                    Format
                  </span>
                  <select
                    value={fmt}
                    onChange={(event) => setFmt(event.target.value as BibliographyFormat)}
                    aria-label="Bibliography format"
                    className={FIELD_CLASS}
                  >
                    {BIBLIOGRAPHY_FORMATS.map(({ value, label }) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                    Added by *
                  </span>
                  <input
                    type="text"
                    value={uploadedBy}
                    onChange={(event) => setUploadedBy(event.target.value)}
                    placeholder="faculty:1"
                    className={FIELD_CLASS}
                  />
                </div>
              </div>

              <div>
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="block text-xs font-medium text-[var(--text-secondary)]">
                    Bibliography *
                  </span>
                  <button
                    type="button"
                    onClick={() => fileRef.current?.click()}
                    className="inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:underline"
                  >
                    <FileUp className="h-3.5 w-3.5" aria-hidden="true" />
                    Load from file (.bib / .ris / .csv)
                  </button>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".bib,.ris,.csv,.txt"
                    className="hidden"
                    aria-hidden="true"
                    tabIndex={-1}
                    onChange={(event) => handleFile(event.target.files?.[0])}
                  />
                </div>
                <textarea
                  ref={firstFieldRef}
                  rows={10}
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder={
                    fmt === "bibtex"
                      ? "@article{key,\n  title = {Paper Title},\n  author = {Curie, Marie},\n  year = {2026},\n}"
                      : fmt === "ris"
                        ? "TY  - JOUR\nTI  - Paper Title\nAU  - Curie, Marie\nPY  - 2026\nER  -"
                        : "title,authors,year,journal,doi\nPaper Title,Curie; Marie,2026,Nature,10.1038/…"
                  }
                  aria-label="Bibliography text"
                  className={cn(FIELD_CLASS, "resize-y font-mono text-xs")}
                />
                <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                  Duplicates (same DOI or title) are skipped and reported — never overwritten.
                </p>
              </div>
            </>
          ) : (
            <div className="space-y-3" aria-live="polite">
              <p className="rounded-lg bg-[var(--success-subtle)] px-3 py-2 text-sm text-[var(--success)]">
                Imported {result.created.length} publication{result.created.length === 1 ? "" : "s"}.
              </p>
              {result.duplicates.length > 0 ? (
                <div className="rounded-lg border border-[var(--warning)] bg-[var(--warning-subtle)] px-3 py-2">
                  <p className="text-sm font-medium text-[var(--warning)]">
                    {result.duplicates.length} duplicate{result.duplicates.length === 1 ? "" : "s"} skipped
                  </p>
                  <ul className="mt-1 space-y-1 text-xs text-[var(--text-secondary)]">
                    {result.duplicates.map((dupe) => (
                      <li key={dupe.index} className="flex items-center gap-1.5">
                        <span className="break-all">
                          “{dupe.title}”{dupe.doi ? ` (${dupe.doi})` : ""} already exists as
                        </span>
                        <a
                          href={`/publications/${encodeURIComponent(dupe.existing_id)}`}
                          className="inline-flex shrink-0 items-center gap-1 text-[var(--accent)] hover:underline"
                        >
                          <Link2 className="h-3 w-3" aria-hidden="true" />
                          existing
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {result.errors.length > 0 ? (
                <div className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2">
                  <p className="text-sm font-medium text-[var(--danger)]">
                    {result.errors.length} entr{result.errors.length === 1 ? "y" : "ies"} failed
                  </p>
                  <ul className="mt-1 space-y-1 text-xs text-[var(--text-secondary)]">
                    {result.errors.map((error) => (
                      <li key={error.index}>
                        #{error.index + 1}
                        {error.title ? ` “${error.title}”` : ""}: {error.message}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          )}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-[var(--border-subtle)] px-5 py-4 sm:flex-row sm:justify-end">
          {result ? (
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
            >
              Done
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? <Spinner /> : null}
                {submitting ? "Importing…" : "Import"}
              </button>
            </>
          )}
        </div>
      </form>
    </div>
  );
}

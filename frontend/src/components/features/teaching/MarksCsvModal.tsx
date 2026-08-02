"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { importMarksCsv } from "@/lib/api/teaching";
import { MARKS_CSV_SAMPLE } from "@/lib/teaching/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { MarksImportResult } from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

/**
 * Import assignment marks from a CSV (PARTS F + G — the Google-Forms loop:
 * the assignment lives in AcademicOS first; responses exported elsewhere
 * come back here as Roll No, Marks, Feedback). The result reports exactly
 * what was graded, which submissions were created on the fly, and row errors.
 */
export function MarksCsvModal({
  open,
  assignmentId,
  onClose,
  onImported,
}: {
  open: boolean;
  assignmentId: string;
  onClose: () => void;
  onImported: (result: MarksImportResult) => void;
}) {
  const [text, setText] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<MarksImportResult | null>(null);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!open) return;
    setText("");
    setFormError(null);
    setResult(null);
    setSubmitting(false);
    submittingRef.current = false;
    setTimeout(() => firstFieldRef.current?.focus(), 50);
  }, [open]);

  if (!open) return null;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);
    if (!text.trim()) {
      setFormError("Paste a marks CSV first (header row required).");
      return;
    }
    submittingRef.current = true;
    setSubmitting(true);
    try {
      const outcome = await importMarksCsv(assignmentId, text, "faculty:ui");
      setResult(outcome);
      submittingRef.current = false;
      setSubmitting(false); // success: the modal stays open — Done must be clickable
      onImported(outcome);
    } catch (err) {
      setFormError(toErrorMessage(err));
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setText(await file.text());
    event.target.value = "";
  };

  const handleClose = () => {
    if (submittingRef.current) return;
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) handleClose();
      }}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="marks-csv-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 id="marks-csv-title" className="text-base font-semibold text-[var(--text-primary)]">
            Import Marks (CSV)
          </h2>
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting}
            aria-label="Close dialog"
            className="rounded-lg p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:opacity-50"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {formError ? (
            <p role="alert" className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
              {formError}
            </p>
          ) : null}

          <p className="text-sm text-[var(--text-secondary)]">
            Google Forms / manual grading: paste the exported CSV — headers
            auto-map (<span className="text-[var(--text-tertiary)]">Roll No, Marks, Feedback</span>).
            Rows above the maximum marks are reported, never clamped silently.
          </p>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">CSV text</span>
            <textarea
              ref={firstFieldRef}
              value={text}
              onChange={(event) => setText(event.target.value)}
              rows={7}
              className={`${FIELD_CLASS} font-mono text-xs`}
              placeholder={MARKS_CSV_SAMPLE}
              aria-label="Marks CSV text"
            />
          </label>

          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]">
            …or choose a .csv file
            <input type="file" accept=".csv,text/csv,text/plain" onChange={handleUpload} className="hidden" aria-label="Choose a CSV file" />
          </label>

          {result ? (
            <div className="space-y-2 rounded-lg border border-[var(--border-subtle)] p-3" aria-live="polite">
              <p className="text-sm font-medium text-[var(--text-primary)]">
                Graded {result.graded.length} submission{result.graded.length === 1 ? "" : "s"}
                {result.created_submissions.length
                  ? ` · ${result.created_submissions.length} created from the CSV`
                  : ""}
                {result.errors.length
                  ? ` · ${result.errors.length} row${result.errors.length === 1 ? "" : "s"} failed`
                  : ""}
              </p>
              {result.errors.map((error) => (
                <p key={`err-${error.index}`} className="text-xs text-[var(--danger)]">
                  Row {error.index + 2}: {error.message}
                </p>
              ))}
            </div>
          ) : null}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[var(--border-subtle)] px-5 py-4">
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting}
            className="rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-50"
          >
            {result ? "Done" : "Cancel"}
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
          >
            {submitting ? <Spinner className="h-4 w-4" /> : null}
            Import marks
          </button>
        </div>
      </form>
    </div>
  );
}

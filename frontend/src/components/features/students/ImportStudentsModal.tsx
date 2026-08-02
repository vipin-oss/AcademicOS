"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { importStudentsCsv } from "@/lib/api/students";
import { STUDENT_IMPORT_HEADERS, STUDENT_IMPORT_SAMPLE } from "@/lib/students/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { StudentImportResult } from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

/**
 * Bulk roster CSV import (PARTS C + F). Headers auto-map server-side — the
 * modal says so up front; the result lists exactly what was created, which
 * rows were skipped as duplicates and which failed, per row (the same
 * result-report pattern as the Publications import).
 */
export function ImportStudentsModal({
  open,
  onClose,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  onImported: (result: StudentImportResult) => void;
}) {
  const [text, setText] = useState("");
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<StudentImportResult | null>(null);
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
      setFormError("Paste a CSV roster first (the first row must be the header).");
      return;
    }
    submittingRef.current = true;
    setSubmitting(true);
    try {
      const outcome = await importStudentsCsv(text, uploadedBy.trim() || "system");
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
        aria-labelledby="import-students-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 id="import-students-title" className="text-base font-semibold text-[var(--text-primary)]">
            Import Students (CSV)
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
            Accepted headers (auto-mapped — spelling variants like
            &quot;Roll_No&quot; / &quot;ROLLNO&quot; are fine):{" "}
            <span className="text-[var(--text-tertiary)]">{STUDENT_IMPORT_HEADERS}</span>
          </p>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
              CSV text
            </span>
            <textarea
              ref={firstFieldRef}
              value={text}
              onChange={(event) => setText(event.target.value)}
              rows={8}
              className={`${FIELD_CLASS} font-mono text-xs`}
              placeholder={STUDENT_IMPORT_SAMPLE}
              aria-label="CSV text"
            />
          </label>

          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]">
              …or choose a .csv file
              <input type="file" accept=".csv,text/csv,text/plain" onChange={handleUpload} className="hidden" aria-label="Choose a CSV file" />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Uploaded by</span>
              <input value={uploadedBy} onChange={(event) => setUploadedBy(event.target.value)} className={FIELD_CLASS} />
            </label>
          </div>

          {result ? (
            <div className="space-y-2 rounded-lg border border-[var(--border-subtle)] p-3" aria-live="polite">
              <p className="text-sm font-medium text-[var(--text-primary)]">
                Imported {result.created.length} student{result.created.length === 1 ? "" : "s"}
                {result.skipped_duplicates.length
                  ? ` · ${result.skipped_duplicates.length} duplicate${result.skipped_duplicates.length === 1 ? "" : "s"} skipped`
                  : ""}
                {result.errors.length
                  ? ` · ${result.errors.length} row${result.errors.length === 1 ? "" : "s"} failed`
                  : ""}
              </p>
              {result.skipped_duplicates.map((dup) => (
                <p key={`dup-${dup.index}`} className="text-xs text-[var(--text-secondary)]">
                  Row {dup.index + 2}: {dup.name ?? ""} ({dup.roll_number ?? ""}) — {dup.message}
                </p>
              ))}
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
            Import
          </button>
        </div>
      </form>
    </div>
  );
}

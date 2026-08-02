"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { recordProgressUpdate } from "@/lib/api/research";
import { Spinner } from "@/components/features/objects/Spinner";
import type { ProjectResponse } from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      {children}
      {hint ? <p className="mt-1 text-xs text-[var(--text-tertiary)]">{hint}</p> : null}
    </label>
  );
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Log a PART 8 progress update ({date, percent, remark}). The API returns the
 * enriched project — the workspace applies it directly (`applyUpdate`), so the
 * completion bar moves without a refetch.
 */
export function ProgressUpdateModal({
  open,
  projectId,
  onClose,
  onSaved,
}: {
  open: boolean;
  projectId: string;
  onClose: () => void;
  onSaved: (project: ProjectResponse) => void;
}) {
  const [date, setDate] = useState("");
  const [percent, setPercent] = useState("");
  const [remark, setRemark] = useState("");
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setDate("");
    setPercent("");
    setRemark("");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
  }, [open]);

  useEffect(() => {
    if (open) firstFieldRef.current?.focus();
  }, [open]);

  if (!open) return null;

  const handleClose = () => {
    if (submittingRef.current) return;
    onClose();
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);

    if (!DATE_RE.test(date.trim())) {
      setFormError("Update date is required (YYYY-MM-DD).");
      return;
    }
    const value = Number(percent.trim());
    if (!percent.trim() || !Number.isFinite(value) || value < 0 || value > 100) {
      setFormError("Completion must be a number between 0 and 100.");
      return;
    }
    if (!remark.trim()) {
      setFormError("A short remark is required.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);
    try {
      const saved = await recordProgressUpdate(projectId, {
        date: date.trim(),
        percent: value,
        remark: remark.trim(),
        uploaded_by: uploadedBy.trim() || "faculty:ui",
      });
      submittingRef.current = false;
      setSubmitting(false);
      onSaved(saved);
    } catch (err) {
      submittingRef.current = false;
      setSubmitting(false);
      setFormError(toErrorMessage(err));
    }
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
        aria-labelledby="progress-update-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-lg flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="progress-update-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            Log progress update
          </h2>
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting}
            aria-label="Close dialog"
            className="rounded-lg p-1.5 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
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

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Date" hint="YYYY-MM-DD.">
              <input
                ref={firstFieldRef}
                value={date}
                onChange={(event) => setDate(event.target.value)}
                className={FIELD_CLASS}
                placeholder="2026-08-02"
                required
              />
            </Field>
            <Field label="Completion (%)">
              <input
                type="number"
                inputMode="numeric"
                min={0}
                max={100}
                value={percent}
                onChange={(event) => setPercent(event.target.value)}
                className={FIELD_CLASS}
                placeholder="40"
                aria-label="Completion percent"
                required
              />
            </Field>
          </div>
          <Field label="Remark">
            <textarea
              value={remark}
              onChange={(event) => setRemark(event.target.value)}
              className={FIELD_CLASS}
              rows={3}
              placeholder="Data collection finished; analysis started."
              required
            />
          </Field>
          <Field label="Added by">
            <input
              value={uploadedBy}
              onChange={(event) => setUploadedBy(event.target.value)}
              className={FIELD_CLASS}
            />
          </Field>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[var(--border-subtle)] px-5 py-4">
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting}
            className="rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
          >
            {submitting ? <Spinner className="h-4 w-4" /> : null}
            Log update
          </button>
        </div>
      </form>
    </div>
  );
}

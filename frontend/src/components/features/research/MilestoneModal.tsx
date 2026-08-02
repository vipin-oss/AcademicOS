"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { addMilestone } from "@/lib/api/research";
import { MILESTONE_STATUSES } from "@/lib/research/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { MilestoneStatus, ProjectMilestone } from "@/types";

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
 * Add a milestone to a project's PART 8 timeline. The API returns the new
 * milestone only — the workspace re-fetches the enriched project payload
 * (`onChanged`) so the dashboard deadlines and timeline stay consistent.
 */
export function MilestoneModal({
  open,
  projectId,
  onClose,
  onSaved,
}: {
  open: boolean;
  projectId: string;
  onClose: () => void;
  onSaved: (milestone: ProjectMilestone) => void;
}) {
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [status, setStatus] = useState<MilestoneStatus>("pending");
  const [notes, setNotes] = useState("");
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setTitle("");
    setDate("");
    setStatus("pending");
    setNotes("");
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

    if (!title.trim()) {
      setFormError("Milestone title must not be empty.");
      return;
    }
    if (!DATE_RE.test(date.trim())) {
      setFormError("Milestone date is required (YYYY-MM-DD).");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);
    try {
      const saved = await addMilestone(projectId, {
        title: title.trim(),
        date: date.trim(),
        status,
        notes: notes.trim() || null,
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
        aria-labelledby="milestone-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-lg flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="milestone-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            Add milestone
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

          <Field label="Milestone title">
            <input
              ref={firstFieldRef}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className={FIELD_CLASS}
              placeholder="Progress report submitted"
              required
            />
          </Field>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Due date" hint="YYYY-MM-DD.">
              <input
                value={date}
                onChange={(event) => setDate(event.target.value)}
                className={FIELD_CLASS}
                placeholder="2026-12-31"
                required
              />
            </Field>
            <Field label="Status">
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value as MilestoneStatus)}
                className={FIELD_CLASS}
                aria-label="Milestone status"
              >
                {MILESTONE_STATUSES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <Field label="Notes">
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className={FIELD_CLASS}
              rows={2}
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
            Add milestone
          </button>
        </div>
      </form>
    </div>
  );
}

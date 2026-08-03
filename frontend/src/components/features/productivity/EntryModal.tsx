"use client";

/**
 * Create / edit a personal calendar entry (PART 2 tail — the only writable
 * calendar source). Same contract as TaskModal / EventModal.
 */
import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { toErrorMessage } from "@/lib/api/client";
import {
  createCalendarEntry,
  updateCalendarEntry,
  type EntryPayload,
} from "@/lib/api/productivity";
import { ENTRY_CATEGORIES } from "@/lib/productivity/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { CalendarEntry } from "@/types";

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

export interface EntrySaveResult {
  entry: CalendarEntry;
  mode: "create" | "edit";
}

export function EntryModal({
  open,
  onClose,
  onSaved,
  entry,
  initialDate,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (result: EntrySaveResult) => void;
  entry?: CalendarEntry | null;
  /** Pre-filled start date when created from a calendar cell. */
  initialDate?: string;
}) {
  const mode = entry ? "edit" : "create";
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [location, setLocation] = useState("");
  const [category, setCategory] = useState("");
  const [tags, setTags] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setTitle(entry?.title ?? "");
    setDescription(entry?.description ?? "");
    setStartDate(entry?.start_date ?? initialDate ?? "");
    setEndDate(entry?.end_date ?? "");
    setStartTime(entry?.start_time ?? "");
    setEndTime(entry?.end_time ?? "");
    setLocation(entry?.location ?? "");
    setCategory(entry?.category ?? "");
    setTags((entry?.tags ?? []).join(", "));
    setFormError(null);
    submittingRef.current = false;
    setSubmitting(false);
  }, [open, entry, initialDate]);

  useEffect(() => {
    if (open) firstFieldRef.current?.focus();
  }, [open]);

  if (!open) return null;

  const handleClose = () => {
    if (submittingRef.current) return;
    onClose();
  };

  const handleSubmit = async (formEvent: React.FormEvent) => {
    formEvent.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);

    if (!title.trim()) {
      setFormError("Entry title must not be empty.");
      return;
    }
    if (!startDate) {
      setFormError("Start date is required.");
      return;
    }
    if (endDate && endDate < startDate) {
      setFormError("End date must not be before the start date.");
      return;
    }
    if (startTime && endTime && startTime > endTime) {
      setFormError("End time must not be before the start time.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);

    const payload: EntryPayload = {
      title: title.trim(),
      start_date: startDate,
      description: description.trim() || undefined,
      end_date: endDate || undefined,
      start_time: startTime || undefined,
      end_time: endTime || undefined,
      location: location.trim() || undefined,
      category: category || undefined,
      tags: tags
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean),
    };

    try {
      const saved = entry
        ? await updateCalendarEntry(entry.id, payload)
        : await createCalendarEntry(payload);
      submittingRef.current = false;
      setSubmitting(false);
      onSaved({ entry: saved, mode });
    } catch (err) {
      submittingRef.current = false;
      setSubmitting(false);
      setFormError(toErrorMessage(err));
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      onMouseDown={(mouseEvent) => {
        if (mouseEvent.target === mouseEvent.currentTarget) handleClose();
      }}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="entry-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 id="entry-modal-title" className="text-base font-semibold text-[var(--text-primary)]">
            {mode === "edit" ? "Edit calendar entry" : "New calendar entry"}
          </h2>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Entry title *">
              <input
                ref={firstFieldRef}
                type="text"
                value={title}
                onChange={(change) => setTitle(change.target.value)}
                aria-label="Entry title"
                className={FIELD_CLASS}
                placeholder="e.g. Doctor's appointment"
              />
            </Field>
            <Field label="Category">
              <select
                value={category}
                onChange={(change) => setCategory(change.target.value)}
                aria-label="Entry category"
                className={FIELD_CLASS}
              >
                <option value="">— none —</option>
                {ENTRY_CATEGORIES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Start date *">
              <input
                type="date"
                value={startDate}
                onChange={(change) => setStartDate(change.target.value)}
                aria-label="Entry start date"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="End date" hint="Leave empty for a single-day entry.">
              <input
                type="date"
                value={endDate}
                onChange={(change) => setEndDate(change.target.value)}
                aria-label="Entry end date"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Start time">
              <input
                type="time"
                value={startTime}
                onChange={(change) => setStartTime(change.target.value)}
                aria-label="Entry start time"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="End time">
              <input
                type="time"
                value={endTime}
                onChange={(change) => setEndTime(change.target.value)}
                aria-label="Entry end time"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Location">
              <input
                type="text"
                value={location}
                onChange={(change) => setLocation(change.target.value)}
                aria-label="Entry location"
                className={FIELD_CLASS}
                placeholder="e.g. City Clinic"
              />
            </Field>
            <Field label="Tags" hint="Comma-separated.">
              <input
                type="text"
                value={tags}
                onChange={(change) => setTags(change.target.value)}
                aria-label="Entry tags"
                className={FIELD_CLASS}
              />
            </Field>
          </div>

          <Field label="Description">
            <textarea
              value={description}
              onChange={(change) => setDescription(change.target.value)}
              aria-label="Entry description"
              rows={3}
              className={FIELD_CLASS}
            />
          </Field>

          {formError ? (
            <p
              role="alert"
              className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
            >
              {formError}
            </p>
          ) : null}
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
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? <Spinner /> : null}
            {submitting ? "Saving…" : mode === "edit" ? "Save changes" : "Create entry"}
          </button>
        </div>
      </form>
    </div>
  );
}

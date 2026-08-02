"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { addMeeting, updateMeeting } from "@/lib/api/committees";
import { MEETING_MODES } from "@/lib/committees/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { MeetingMode, MeetingResponse } from "@/types";

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

export interface MeetingSaveResult {
  meeting: MeetingResponse;
  mode: "create" | "edit";
}

/**
 * Schedule / edit a meeting (PART 3 identity). Agenda, attendance, minutes
 * and decisions are managed on the meeting workspace afterwards.
 */
export function MeetingModal({
  open,
  committeeId,
  onClose,
  onSaved,
  meeting,
}: {
  open: boolean;
  /** Required in create mode — the meeting hangs off this committee. */
  committeeId?: string;
  onClose: () => void;
  onSaved: (result: MeetingSaveResult) => void;
  meeting?: MeetingResponse | null;
}) {
  const mode = meeting ? "edit" : "create";
  const [title, setTitle] = useState("");
  const [meetingNumber, setMeetingNumber] = useState("");
  const [meetingDate, setMeetingDate] = useState("");
  const [venue, setVenue] = useState("");
  const [meetingMode, setMeetingMode] = useState<MeetingMode | "">("");
  const [remarks, setRemarks] = useState("");
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setTitle(meeting?.title ?? "");
    setMeetingNumber(meeting?.meeting_number ?? "");
    setMeetingDate(meeting?.meeting_date ?? "");
    setVenue(meeting?.venue ?? "");
    setMeetingMode(meeting?.mode ?? "");
    setRemarks(meeting?.remarks ?? "");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
  }, [open, meeting]);

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
      setFormError("Meeting title must not be empty.");
      return;
    }
    if (!meeting && !committeeId) {
      setFormError("No committee selected for this meeting.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);

    const payload = {
      title: title.trim(),
      uploaded_by: uploadedBy.trim() || "faculty:ui",
      meeting_number: meetingNumber.trim() || null,
      meeting_date: meetingDate.trim() || null,
      venue: venue.trim() || null,
      mode: (meetingMode || null) as MeetingMode | null,
      remarks: remarks.trim() || null,
    };

    try {
      const saved =
        meeting
          ? await updateMeeting(meeting.id, payload)
          : await addMeeting(committeeId as string, payload);
      submittingRef.current = false;
      setSubmitting(false);
      onSaved({ meeting: saved, mode });
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
        aria-labelledby="meeting-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="meeting-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            {mode === "edit" ? "Edit meeting" : "New meeting"}
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
          <Field label="Meeting title *">
            <input
              ref={firstFieldRef}
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. 12th Purchase Committee Meeting"
              className={FIELD_CLASS}
            />
          </Field>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field
              label="Meeting number"
              hint="Unique within the committee (409 on duplicates)."
            >
              <input
                type="text"
                value={meetingNumber}
                onChange={(event) => setMeetingNumber(event.target.value)}
                placeholder="e.g. 12"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Meeting date">
              <input
                type="date"
                value={meetingDate}
                onChange={(event) => setMeetingDate(event.target.value)}
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Venue">
              <input
                type="text"
                value={venue}
                onChange={(event) => setVenue(event.target.value)}
                placeholder="e.g. Board Room 2"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Mode">
              <select
                value={meetingMode}
                onChange={(event) => setMeetingMode(event.target.value as MeetingMode | "")}
                className={FIELD_CLASS}
              >
                <option value="">— Select mode —</option>
                {MEETING_MODES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <Field label="Remarks">
            <textarea
              value={remarks}
              onChange={(event) => setRemarks(event.target.value)}
              rows={2}
              className={FIELD_CLASS}
            />
          </Field>
          <Field label="Recorded by" hint="Audit attribution (the wire key is uploaded_by).">
            <input
              type="text"
              value={uploadedBy}
              onChange={(event) => setUploadedBy(event.target.value)}
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

        <div className="flex flex-col-reverse gap-2 border-t border-[var(--border-subtle)] px-5 py-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={handleClose}
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
            {submitting
              ? mode === "edit"
                ? "Saving…"
                : "Creating…"
              : mode === "edit"
                ? "Save changes"
                : "Create meeting"}
          </button>
        </div>
      </form>
    </div>
  );
}

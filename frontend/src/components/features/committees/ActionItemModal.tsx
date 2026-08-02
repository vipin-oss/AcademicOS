"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { addActionItem, updateActionItem } from "@/lib/api/committees";
import { listFaculty } from "@/lib/api/faculty";
import { ACTION_PRIORITIES, ACTION_STATUSES } from "@/lib/committees/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { ActionItem, ActionPriority, ActionStatus } from "@/types";

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

export interface ActionItemSaveResult {
  action: ActionItem;
  mode: "create" | "edit";
}

/**
 * PART 5 action item. Assignees are faculty records (the backend rejects
 * other object types with 422); progress is clamped 0..100 server-side.
 */
export function ActionItemModal({
  open,
  meetingId,
  onClose,
  onSaved,
  action,
}: {
  open: boolean;
  /** Required in create mode — the item hangs off this meeting. */
  meetingId?: string;
  onClose: () => void;
  onSaved: (result: ActionItemSaveResult) => void;
  action?: ActionItem | null;
}) {
  const mode = action ? "edit" : "create";
  const [title, setTitle] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [priority, setPriority] = useState<ActionPriority | "">("");
  const [actionStatus, setActionStatus] = useState<ActionStatus>("pending");
  const [progress, setProgress] = useState("0");
  const [completionDate, setCompletionDate] = useState("");
  const [remarks, setRemarks] = useState("");
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);
  const [facultyOptions, setFacultyOptions] = useState<{ id: string; label: string }[]>([]);

  useEffect(() => {
    if (!open) return;
    setTitle(action?.title ?? "");
    setAssignedTo(action?.assigned_to ?? "");
    setDueDate(action?.due_date ?? "");
    setPriority((action?.priority as ActionPriority | "") ?? "");
    setActionStatus(action?.status ?? "pending");
    setProgress(String(action?.progress ?? 0));
    setCompletionDate(action?.completion_date ?? "");
    setRemarks(action?.remarks ?? "");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
  }, [open, action]);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    listFaculty({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setFacultyOptions(
          response.items.map((person) => ({ id: person.id, label: person.name })),
        ),
      )
      .catch(() => setFacultyOptions([]));
    return () => controller.abort();
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
      setFormError("Action title must not be empty.");
      return;
    }
    if (!action && !meetingId) {
      setFormError("No meeting selected for this action item.");
      return;
    }
    const parsedProgress = progress.trim() ? Number(progress.trim()) : 0;
    if (!Number.isFinite(parsedProgress) || parsedProgress < 0 || parsedProgress > 100) {
      setFormError("Progress must be an integer between 0 and 100.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);

    const payload = {
      title: title.trim(),
      uploaded_by: uploadedBy.trim() || "faculty:ui",
      assigned_to: assignedTo || null,
      due_date: dueDate.trim() || null,
      priority: (priority || null) as ActionPriority | null,
      status: actionStatus,
      progress: Math.round(parsedProgress),
      completion_date: completionDate.trim() || null,
      remarks: remarks.trim() || null,
    };

    try {
      const saved = action
        ? await updateActionItem(action.id, payload)
        : await addActionItem(meetingId as string, payload);
      submittingRef.current = false;
      setSubmitting(false);
      onSaved({ action: saved, mode });
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
        aria-labelledby="action-item-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="action-item-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            {mode === "edit" ? "Edit action item" : "New action item"}
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
          <Field label="Action title *">
            <input
              ref={firstFieldRef}
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. Circulate revised vendor comparison sheet"
              className={FIELD_CLASS}
            />
          </Field>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Assigned to" hint="Faculty member responsible.">
              <select
                value={assignedTo}
                onChange={(event) => setAssignedTo(event.target.value)}
                className={FIELD_CLASS}
              >
                <option value="">— Unassigned —</option>
                {facultyOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Due date">
              <input
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Priority">
              <select
                value={priority}
                onChange={(event) => setPriority(event.target.value as ActionPriority | "")}
                className={FIELD_CLASS}
              >
                <option value="">— Select —</option>
                {ACTION_PRIORITIES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Status">
              <select
                value={actionStatus}
                onChange={(event) => setActionStatus(event.target.value as ActionStatus)}
                className={FIELD_CLASS}
              >
                {ACTION_STATUSES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Progress (%)" hint="0–100.">
              <input
                type="number"
                inputMode="numeric"
                min={0}
                max={100}
                value={progress}
                onChange={(event) => setProgress(event.target.value)}
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Completion date">
              <input
                type="date"
                value={completionDate}
                onChange={(event) => setCompletionDate(event.target.value)}
                className={FIELD_CLASS}
              />
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
                : "Create action"}
          </button>
        </div>
      </form>
    </div>
  );
}

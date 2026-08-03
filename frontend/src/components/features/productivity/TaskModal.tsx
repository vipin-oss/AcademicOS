"use client";

/**
 * Create / edit a Personal Task (PART 3). Mirrors the EventModal contract:
 * role="dialog" form, focus-on-open, submittingRef guard, server errors via
 * toErrorMessage, and a { task, mode } save result.
 */
import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { toErrorMessage } from "@/lib/api/client";
import { createTask, updateTask, type TaskPayload } from "@/lib/api/productivity";
import { TASK_CATEGORIES, TASK_PRIORITIES } from "@/lib/productivity/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { ProductivityTask } from "@/types";

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

export interface TaskSaveResult {
  task: ProductivityTask;
  mode: "create" | "edit";
}

export function TaskModal({
  open,
  onClose,
  onSaved,
  task,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (result: TaskSaveResult) => void;
  task?: ProductivityTask | null;
}) {
  const mode = task ? "edit" : "create";
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("");
  const [category, setCategory] = useState("");
  const [startDate, setStartDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [reminder, setReminder] = useState("");
  const [completed, setCompleted] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [tags, setTags] = useState("");
  const [remarks, setRemarks] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setTitle(task?.title ?? "");
    setDescription(task?.description ?? "");
    setPriority(task?.priority ?? "");
    setCategory(task?.category ?? "");
    setStartDate(task?.start_date ?? "");
    setDueDate(task?.due_date ?? "");
    setReminder(task?.reminder ?? "");
    setCompleted(task?.completed ?? false);
    setPinned(task?.pinned ?? false);
    setTags((task?.tags ?? []).join(", "));
    setRemarks(task?.remarks ?? "");
    setFormError(null);
    submittingRef.current = false;
    setSubmitting(false);
  }, [open, task]);

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
      setFormError("Task title must not be empty.");
      return;
    }
    if (startDate && dueDate && dueDate < startDate) {
      setFormError("Due date must not be before the start date.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);

    const payload: TaskPayload = {
      title: title.trim(),
      description: description.trim() || undefined,
      priority: priority || undefined,
      category: category || undefined,
      start_date: startDate || undefined,
      due_date: dueDate || undefined,
      reminder: reminder || undefined,
      completed,
      pinned,
      tags: tags
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean),
      remarks: remarks.trim() || undefined,
    };

    try {
      const saved = task ? await updateTask(task.id, payload) : await createTask(payload);
      submittingRef.current = false;
      setSubmitting(false);
      onSaved({ task: saved, mode });
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
        aria-labelledby="task-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 id="task-modal-title" className="text-base font-semibold text-[var(--text-primary)]">
            {mode === "edit" ? "Edit task" : "New task"}
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
            <Field label="Task title *">
              <input
                ref={firstFieldRef}
                type="text"
                value={title}
                onChange={(change) => setTitle(change.target.value)}
                aria-label="Task title"
                className={FIELD_CLASS}
                placeholder="e.g. Review NAAC evidence folder"
              />
            </Field>
            <Field label="Category">
              <select
                value={category}
                onChange={(change) => setCategory(change.target.value)}
                aria-label="Task category"
                className={FIELD_CLASS}
              >
                <option value="">— none —</option>
                {TASK_CATEGORIES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Priority">
              <select
                value={priority}
                onChange={(change) => setPriority(change.target.value)}
                aria-label="Task priority"
                className={FIELD_CLASS}
              >
                <option value="">— none —</option>
                {TASK_PRIORITIES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Tags" hint="Comma-separated, e.g. naac, evidence.">
              <input
                type="text"
                value={tags}
                onChange={(change) => setTags(change.target.value)}
                aria-label="Task tags"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Start date">
              <input
                type="date"
                value={startDate}
                onChange={(change) => setStartDate(change.target.value)}
                aria-label="Task start date"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Due date">
              <input
                type="date"
                value={dueDate}
                onChange={(change) => setDueDate(change.target.value)}
                aria-label="Task due date"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Reminder on">
              <input
                type="date"
                value={reminder}
                onChange={(change) => setReminder(change.target.value)}
                aria-label="Task reminder date"
                className={FIELD_CLASS}
              />
            </Field>
            <div className="flex items-end gap-6 pb-1">
              <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                <input
                  type="checkbox"
                  checked={completed}
                  onChange={(change) => setCompleted(change.target.checked)}
                  aria-label="Task completed"
                  className="h-4 w-4 rounded border-[var(--border-subtle)] accent-[var(--accent)]"
                />
                Completed
              </label>
              <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                <input
                  type="checkbox"
                  checked={pinned}
                  onChange={(change) => setPinned(change.target.checked)}
                  aria-label="Task pinned"
                  className="h-4 w-4 rounded border-[var(--border-subtle)] accent-[var(--accent)]"
                />
                Pinned
              </label>
            </div>
          </div>

          <Field label="Description">
            <textarea
              value={description}
              onChange={(change) => setDescription(change.target.value)}
              aria-label="Task description"
              rows={3}
              className={FIELD_CLASS}
            />
          </Field>
          <Field label="Remarks">
            <input
              type="text"
              value={remarks}
              onChange={(change) => setRemarks(change.target.value)}
              aria-label="Task remarks"
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
            {submitting ? "Saving…" : mode === "edit" ? "Save changes" : "Create task"}
          </button>
        </div>
      </form>
    </div>
  );
}

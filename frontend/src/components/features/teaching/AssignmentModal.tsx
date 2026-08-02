"use client";

import { useEffect, useRef, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { createClassAssignment, updateAssignment } from "@/lib/api/teaching";
import { ASSIGNMENT_TYPES } from "@/lib/teaching/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { AssignmentResponse, AssignmentTypeValue, RubricCriterion } from "@/types";

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

export interface AssignmentSaveResult {
  assignment: AssignmentResponse;
  mode: "create" | "edit";
}

/** ISO/date accepted by the backend; datetime-local gives "YYYY-MM-DDTHH:mm". */
function toApiDeadline(local: string): string | null {
  const trimmed = local.trim();
  return trimmed ? trimmed : null;
}

function toLocalInput(raw: string | null | undefined): string {
  if (!raw) return "";
  return raw.length >= 16 ? raw.slice(0, 16) : raw;
}

/** Create / edit an Assignment (PART D — every field from the spec). */
export function AssignmentModal({
  open,
  classId,
  onClose,
  onSaved,
  assignment,
}: {
  open: boolean;
  classId: string;
  onClose: () => void;
  onSaved: (result: AssignmentSaveResult) => void;
  assignment?: AssignmentResponse | null;
}) {
  const mode = assignment ? "edit" : "create";
  const [title, setTitle] = useState("");
  const [assignmentType, setAssignmentType] = useState<AssignmentTypeValue>("assignment");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [maxMarks, setMaxMarks] = useState("");
  const [deadline, setDeadline] = useState("");
  const [lateAllowed, setLateAllowed] = useState(false);
  const [weightage, setWeightage] = useState("");
  const [visibility, setVisibility] = useState<"visible" | "hidden">("visible");
  const [rubric, setRubric] = useState<RubricCriterion[]>([]);
  const [status, setStatus] = useState<"draft" | "active" | "archived">("active");
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setTitle(assignment?.title ?? "");
    setAssignmentType(assignment?.assignment_type ?? "assignment");
    setDescription(assignment?.description ?? "");
    setInstructions(assignment?.instructions ?? "");
    setMaxMarks(assignment?.max_marks != null ? String(assignment.max_marks) : "");
    setDeadline(toLocalInput(assignment?.deadline));
    setLateAllowed(assignment?.late_allowed ?? false);
    setWeightage(assignment?.weightage != null ? String(assignment.weightage) : "");
    setVisibility(assignment?.visibility ?? "visible");
    setRubric(assignment?.rubric ?? []);
    setStatus(assignment?.status ?? "active");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
    setTimeout(() => firstFieldRef.current?.focus(), 50);
  }, [open, assignment]);

  if (!open) return null;

  const updateRubricRow = (index: number, patch: Partial<RubricCriterion>) => {
    setRubric((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);

    if (!title.trim()) {
      setFormError("Assignment title must not be empty.");
      return;
    }
    const maxNumber = maxMarks.trim() ? Number(maxMarks.trim()) : null;
    if (maxNumber != null && (Number.isNaN(maxNumber) || maxNumber < 0)) {
      setFormError("Max marks must be a non-negative number.");
      return;
    }
    const weightageNumber = weightage.trim() ? Number(weightage.trim()) : null;
    if (weightageNumber != null && (Number.isNaN(weightageNumber) || weightageNumber < 0 || weightageNumber > 100)) {
      setFormError("Weightage must be a percentage between 0 and 100.");
      return;
    }

    const payload = {
      title: title.trim(),
      uploaded_by: uploadedBy.trim() || "system",
      assignment_type: assignmentType,
      status,
      description: description.trim() || null,
      instructions: instructions.trim() || null,
      max_marks: maxNumber,
      deadline: toApiDeadline(deadline),
      late_allowed: lateAllowed,
      rubric: rubric.filter((row) => row.criterion.trim()),
      visibility,
      weightage: weightageNumber,
    };

    submittingRef.current = true;
    setSubmitting(true);
    try {
      const saved = assignment
        ? await updateAssignment(assignment.id, payload)
        : await createClassAssignment(classId, payload);
      onSaved({ assignment: saved, mode });
    } catch (err) {
      setFormError(toErrorMessage(err));
      submittingRef.current = false;
      setSubmitting(false);
    }
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
        aria-labelledby="assignment-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 id="assignment-modal-title" className="text-base font-semibold text-[var(--text-primary)]">
            {mode === "edit" ? "Edit Assignment" : "New Assignment"}
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

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          {formError ? (
            <p role="alert" className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
              {formError}
            </p>
          ) : null}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Title">
              <input
                ref={firstFieldRef}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className={FIELD_CLASS}
                placeholder="Assignment 1 — Python Basics"
                required
              />
            </Field>
            <Field label="Assessment type">
              <select
                value={assignmentType}
                onChange={(event) => setAssignmentType(event.target.value as AssignmentTypeValue)}
                className={FIELD_CLASS}
                aria-label="Assessment type"
              >
                {ASSIGNMENT_TYPES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Description">
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} className={FIELD_CLASS} rows={2} />
          </Field>
          <Field label="Instructions" hint="Shown to students with the submission form.">
            <textarea value={instructions} onChange={(event) => setInstructions(event.target.value)} className={FIELD_CLASS} rows={2} />
          </Field>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Field label="Maximum marks">
              <input type="number" min={0} step="0.5" value={maxMarks} onChange={(event) => setMaxMarks(event.target.value)} className={FIELD_CLASS} />
            </Field>
            <Field label="Submission deadline">
              <input type="datetime-local" value={deadline} onChange={(event) => setDeadline(event.target.value)} className={FIELD_CLASS} />
            </Field>
            <Field label="Weightage (%)" hint="Share of the total — powers the automatic gradebook.">
              <input type="number" min={0} max={100} step="1" value={weightage} onChange={(event) => setWeightage(event.target.value)} className={FIELD_CLASS} />
            </Field>
          </div>

          <div className="flex flex-wrap gap-6">
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={lateAllowed}
                onChange={(event) => setLateAllowed(event.target.checked)}
                className="h-4 w-4 accent-[var(--accent)]"
              />
              Late submission allowed
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <span>Visibility:</span>
              <select
                value={visibility}
                onChange={(event) => setVisibility(event.target.value as "visible" | "hidden")}
                className={FIELD_CLASS}
                aria-label="Visibility"
              >
                <option value="visible">Visible</option>
                <option value="hidden">Hidden</option>
              </select>
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <span>Status:</span>
              <select value={status} onChange={(event) => setStatus(event.target.value as "draft" | "active" | "archived")} className={FIELD_CLASS} aria-label="Status">
                <option value="draft">Draft</option>
                <option value="active">Active</option>
                <option value="archived">Archived</option>
              </select>
            </label>
          </div>

          <div className="space-y-2">
            <span className="block text-xs font-medium text-[var(--text-secondary)]">
              Rubric (optional)
            </span>
            {rubric.map((row, index) => (
              <div key={index} className="grid grid-cols-[1fr_6rem_auto] items-center gap-2">
                <input
                  value={row.criterion}
                  onChange={(event) => updateRubricRow(index, { criterion: event.target.value })}
                  className={FIELD_CLASS}
                  placeholder="Criterion (e.g. Correctness)"
                  aria-label={`Rubric criterion ${index + 1}`}
                />
                <input
                  type="number"
                  min={0}
                  step="0.5"
                  value={row.marks ?? ""}
                  onChange={(event) =>
                    updateRubricRow(index, {
                      marks: event.target.value ? Number(event.target.value) : undefined,
                    })
                  }
                  className={FIELD_CLASS}
                  placeholder="Marks"
                  aria-label={`Rubric marks ${index + 1}`}
                />
                <button
                  type="button"
                  onClick={() => setRubric((rows) => rows.filter((_, i) => i !== index))}
                  aria-label={`Remove rubric row ${index + 1}`}
                  className="rounded-lg p-2 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--danger)]"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setRubric((rows) => [...rows, { criterion: "", marks: undefined }])}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add criterion
            </button>
          </div>

          <Field label="Uploaded by">
            <input value={uploadedBy} onChange={(event) => setUploadedBy(event.target.value)} className={FIELD_CLASS} />
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
            {mode === "edit" ? "Save changes" : "Create assignment"}
          </button>
        </div>
      </form>
    </div>
  );
}

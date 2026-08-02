"use client";

import { useEffect, useRef, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { createClass, updateClass } from "@/lib/api/teaching";
import { CLASS_MODES, WEEKDAYS } from "@/lib/teaching/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { ClassResponse, WeeklySlot } from "@/types";

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

export interface ClassSaveResult {
  cls: ClassResponse;
  mode: "create" | "edit";
}

interface SlotRow {
  day: string;
  start: string;
  end: string;
}

/**
 * Create / edit a Class (PART B: title, course code, programme, semester,
 * section, session, credits, weekly schedule, room, mode, teacher ids).
 * "Every class becomes a reusable academic object."
 */
export function ClassModal({
  open,
  onClose,
  onSaved,
  cls,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (result: ClassSaveResult) => void;
  cls?: ClassResponse | null;
}) {
  const mode = cls ? "edit" : "create";
  const [title, setTitle] = useState("");
  const [courseCode, setCourseCode] = useState("");
  const [programme, setProgramme] = useState("");
  const [semester, setSemester] = useState("");
  const [section, setSection] = useState("");
  const [session, setSession] = useState("");
  const [credits, setCredits] = useState("");
  const [room, setRoom] = useState("");
  const [classMode, setClassMode] = useState("offline");
  const [slots, setSlots] = useState<SlotRow[]>([]);
  const [teacherIds, setTeacherIds] = useState("");
  const [notes, setNotes] = useState("");
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [status, setStatus] = useState<"draft" | "active" | "archived">("active");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setTitle(cls?.title ?? "");
    setCourseCode(cls?.course_code ?? "");
    setProgramme(cls?.programme ?? "");
    setSemester(cls?.semester != null ? String(cls.semester) : "");
    setSection(cls?.section ?? "");
    setSession(cls?.session ?? "");
    setCredits(cls?.credits != null ? String(cls.credits) : "");
    setRoom(cls?.room ?? "");
    setClassMode(cls?.class_mode ?? "offline");
    setSlots(
      (cls?.weekly_schedule ?? []).map((slot) => ({
        day: slot.day,
        start: slot.start ?? "",
        end: slot.end ?? "",
      })),
    );
    setTeacherIds(
      (cls?.links.teachers ?? []).map((teacher) => teacher.id).join(", "),
    );
    setNotes(cls?.notes ?? "");
    setStatus(cls?.status ?? "active");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
    setTimeout(() => firstFieldRef.current?.focus(), 50);
  }, [open, cls]);

  if (!open) return null;

  const updateSlot = (index: number, patch: Partial<SlotRow>) => {
    setSlots((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);

    if (!title.trim()) {
      setFormError("Class title must not be empty.");
      return;
    }
    const semesterNumber = semester.trim() ? Number(semester.trim()) : null;
    if (semesterNumber != null && (!Number.isInteger(semesterNumber) || semesterNumber < 1 || semesterNumber > 12)) {
      setFormError("Semester must be a number between 1 and 12.");
      return;
    }
    const creditsNumber = credits.trim() ? Number(credits.trim()) : null;
    if (creditsNumber != null && (Number.isNaN(creditsNumber) || creditsNumber < 0)) {
      setFormError("Credits must be a non-negative number.");
      return;
    }

    const teachers = teacherIds
      .split(/[,;\s]+/)
      .map((part) => part.trim())
      .filter(Boolean);

    const payload = {
      title: title.trim(),
      uploaded_by: uploadedBy.trim() || "system",
      status,
      course_code: courseCode.trim() || null,
      programme: programme.trim() || null,
      semester: semesterNumber,
      section: section.trim() || null,
      session: session.trim() || null,
      credits: creditsNumber,
      weekly_schedule: slots
        .filter((slot) => slot.day)
        .map((slot) => ({ day: slot.day, start: slot.start, end: slot.end }) as WeeklySlot),
      room: room.trim() || null,
      class_mode: classMode || null,
      notes: notes.trim() || null,
      ...(teachers.length > 0 || mode === "edit" ? { links: { teachers } } : {}),
    };

    submittingRef.current = true;
    setSubmitting(true);
    try {
      const saved = cls ? await updateClass(cls.id, payload) : await createClass(payload);
      onSaved({ cls: saved, mode });
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
        aria-labelledby="class-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 id="class-modal-title" className="text-base font-semibold text-[var(--text-primary)]">
            {mode === "edit" ? "Edit Class" : "Create Class"}
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

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Course identity
            </legend>
            <Field label="Class title">
              <input
                ref={firstFieldRef}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className={FIELD_CLASS}
                placeholder="Computer Fundamentals"
                required
              />
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Course code">
                <input value={courseCode} onChange={(event) => setCourseCode(event.target.value)} className={FIELD_CLASS} placeholder="CS-101" />
              </Field>
              <Field label="Programme">
                <input value={programme} onChange={(event) => setProgramme(event.target.value)} className={FIELD_CLASS} placeholder="BSc Mathematics with Data Science" />
              </Field>
              <Field label="Semester">
                <input type="number" min={1} max={12} value={semester} onChange={(event) => setSemester(event.target.value)} className={FIELD_CLASS} />
              </Field>
              <Field label="Section">
                <input value={section} onChange={(event) => setSection(event.target.value)} className={FIELD_CLASS} placeholder="A" />
              </Field>
              <Field label="Session" hint="Academic session, e.g. 2026-27.">
                <input value={session} onChange={(event) => setSession(event.target.value)} className={FIELD_CLASS} placeholder="2026-27" />
              </Field>
              <Field label="Credits">
                <input type="number" min={0} step="0.5" value={credits} onChange={(event) => setCredits(event.target.value)} className={FIELD_CLASS} />
              </Field>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Schedule & mode
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Room">
                <input value={room} onChange={(event) => setRoom(event.target.value)} className={FIELD_CLASS} placeholder="LH-2" />
              </Field>
              <Field label="Class mode">
                <select value={classMode} onChange={(event) => setClassMode(event.target.value)} className={FIELD_CLASS} aria-label="Class mode">
                  {CLASS_MODES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <div className="space-y-2">
              <span className="block text-xs font-medium text-[var(--text-secondary)]">Weekly schedule</span>
              {slots.map((slot, index) => (
                <div key={index} className="grid grid-cols-[1fr_1fr_1fr_auto] items-center gap-2">
                  <select
                    value={slot.day}
                    onChange={(event) => updateSlot(index, { day: event.target.value })}
                    className={FIELD_CLASS}
                    aria-label={`Schedule day ${index + 1}`}
                  >
                    {WEEKDAYS.map((day) => (
                      <option key={day.value} value={day.value}>
                        {day.label}
                      </option>
                    ))}
                  </select>
                  <input
                    type="time"
                    value={slot.start}
                    onChange={(event) => updateSlot(index, { start: event.target.value })}
                    className={FIELD_CLASS}
                    aria-label={`Start time ${index + 1}`}
                  />
                  <input
                    type="time"
                    value={slot.end}
                    onChange={(event) => updateSlot(index, { end: event.target.value })}
                    className={FIELD_CLASS}
                    aria-label={`End time ${index + 1}`}
                  />
                  <button
                    type="button"
                    onClick={() => setSlots((rows) => rows.filter((_, i) => i !== index))}
                    aria-label={`Remove schedule row ${index + 1}`}
                    className="rounded-lg p-2 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--danger)]"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setSlots((rows) => [...rows, { day: "mon", start: "09:00", end: "10:00" }])}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add slot
              </button>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Teachers & administration
            </legend>
            <Field label="Teacher object ids" hint="Comma-separated faculty Object ids (the TAUGHT_BY edge).">
              <input value={teacherIds} onChange={(event) => setTeacherIds(event.target.value)} className={FIELD_CLASS} placeholder="obj:faculty:…" />
            </Field>
            <Field label="Notes">
              <textarea value={notes} onChange={(event) => setNotes(event.target.value)} className={FIELD_CLASS} rows={2} />
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Status">
                <select value={status} onChange={(event) => setStatus(event.target.value as "draft" | "active" | "archived")} className={FIELD_CLASS} aria-label="Status">
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="archived">Archived</option>
                </select>
              </Field>
              <Field label="Uploaded by">
                <input value={uploadedBy} onChange={(event) => setUploadedBy(event.target.value)} className={FIELD_CLASS} />
              </Field>
            </div>
          </fieldset>
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
            {mode === "edit" ? "Save changes" : "Create class"}
          </button>
        </div>
      </form>
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { listStudents } from "@/lib/api/students";
import { enrollFromCsv, enrollStudents } from "@/lib/api/teaching";
import { STUDENT_CSV_SAMPLE } from "@/lib/teaching/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { EnrollmentResult, StudentResponse } from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

/**
 * Enroll students into a Class (PART C): Manual (pick from the registry)
 * or CSV Import (roll numbers / emails — headers auto-map). The result
 * reports exactly what enrolled, what was already enrolled and what failed.
 */
export function EnrollModal({
  open,
  classId,
  enrolledIds,
  onClose,
  onEnrolled,
}: {
  open: boolean;
  classId: string;
  /** Students already on the roster (pre-checked + disabled). */
  enrolledIds: Set<string>;
  onClose: () => void;
  onEnrolled: (result: EnrollmentResult) => void;
}) {
  const [tab, setTab] = useState<"manual" | "csv">("manual");
  const [students, setStudents] = useState<StudentResponse[]>([]);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const [studentsError, setStudentsError] = useState<string | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [csvText, setCsvText] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);

  useEffect(() => {
    if (!open) return;
    setTab("manual");
    setChecked(new Set());
    setCsvText("");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
    setStudentsLoading(true);
    setStudentsError(null);
    listStudents({ pageSize: 100 })
      .then((response) => setStudents(response.items))
      .catch((err) => setStudentsError(toErrorMessage(err)))
      .finally(() => setStudentsLoading(false));
  }, [open]);

  if (!open) return null;

  const toggle = (id: string) => {
    setChecked((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);

    submittingRef.current = true;
    setSubmitting(true);
    try {
      const result =
        tab === "manual"
          ? await enrollStudents(classId, [...checked], "faculty:ui")
          : await enrollFromCsv(classId, csvText, "faculty:ui");
      onEnrolled(result);
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
        aria-labelledby="enroll-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 id="enroll-modal-title" className="text-base font-semibold text-[var(--text-primary)]">
            Enroll Students
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

          <div role="tablist" aria-label="Enrollment mode" className="flex gap-2">
            {(["manual", "csv"] as const).map((value) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={tab === value}
                onClick={() => setTab(value)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  tab === value
                    ? "bg-[var(--accent-subtle)] text-[var(--accent)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                }`}
              >
                {value === "manual" ? "Pick students" : "CSV import"}
              </button>
            ))}
          </div>

          {tab === "manual" ? (
            <div className="max-h-72 overflow-y-auto rounded-lg border border-[var(--border-subtle)]">
              {studentsLoading ? (
                <p className="flex items-center gap-2 px-3 py-3 text-sm text-[var(--text-tertiary)]">
                  <Spinner className="h-4 w-4" /> Loading students…
                </p>
              ) : studentsError ? (
                <p className="px-3 py-3 text-sm text-[var(--danger)]">{studentsError}</p>
              ) : students.length === 0 ? (
                <p className="px-3 py-3 text-sm text-[var(--text-tertiary)]">
                  No students in the registry yet — admit them under Students first.
                </p>
              ) : (
                <ul className="divide-y divide-[var(--border-subtle)]">
                  {students.map((student) => {
                    const enrolled = enrolledIds.has(student.id);
                    return (
                      <li key={student.id}>
                        <label className="flex cursor-pointer items-center gap-2.5 px-3 py-2 text-sm hover:bg-[var(--bg-hover)]">
                          <input
                            type="checkbox"
                            checked={enrolled || checked.has(student.id)}
                            disabled={enrolled}
                            onChange={() => toggle(student.id)}
                            aria-label={`Enroll ${student.name}`}
                            className="h-4 w-4 accent-[var(--accent)]"
                          />
                          <span className="flex-1 text-[var(--text-primary)]">
                            {student.name}
                            {enrolled ? (
                              <span className="ml-2 text-xs text-[var(--text-tertiary)]">
                                (already enrolled)
                              </span>
                            ) : null}
                          </span>
                          <span className="text-xs text-[var(--text-tertiary)]">
                            {student.roll_number ?? ""}
                          </span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-[var(--text-secondary)]">
                One row per student — roll number or email (existing students
                only; the header row is required).
              </p>
              <textarea
                value={csvText}
                onChange={(event) => setCsvText(event.target.value)}
                rows={6}
                className={`${FIELD_CLASS} font-mono text-xs`}
                placeholder={STUDENT_CSV_SAMPLE}
                aria-label="Enrollment CSV text"
              />
            </div>
          )}
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
            disabled={
              submitting || (tab === "manual" ? checked.size === 0 : !csvText.trim())
            }
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
          >
            {submitting ? <Spinner className="h-4 w-4" /> : null}
            Enroll
          </button>
        </div>
      </form>
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { createStudent, updateStudent } from "@/lib/api/students";
import { STUDENT_TYPES } from "@/lib/students/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { StudentResponse, StudentTypeValue } from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

function Field({
  label,
  error,
  hint,
  children,
}: {
  label: string;
  error?: string | null;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      {children}
      {error ? (
        <p role="alert" className="mt-1 text-xs text-[var(--danger)]">
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1 text-xs text-[var(--text-tertiary)]">{hint}</p>
      ) : null}
    </label>
  );
}

export interface StudentSaveResult {
  student: StudentResponse;
  mode: "create" | "edit";
}

/**
 * Admit / edit a Student. Create mode posts the full registry record; edit
 * mode PUTs every field (the backend's merge contract keeps it consistent).
 */
export function StudentModal({
  open,
  onClose,
  onSaved,
  student,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (result: StudentSaveResult) => void;
  student?: StudentResponse | null;
}) {
  const mode = student ? "edit" : "create";
  const [name, setName] = useState("");
  const [studentType, setStudentType] = useState<StudentTypeValue>("ug");
  const [roll, setRoll] = useState("");
  const [registration, setRegistration] = useState("");
  const [enrollment, setEnrollment] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [programme, setProgramme] = useState("");
  const [department, setDepartment] = useState("");
  const [semester, setSemester] = useState("");
  const [section, setSection] = useState("");
  const [batch, setBatch] = useState("");
  const [admissionDate, setAdmissionDate] = useState("");
  const [graduation, setGraduation] = useState("");
  const [researchArea, setResearchArea] = useState("");
  const [orcid, setOrcid] = useState("");
  const [scholar, setScholar] = useState("");
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState("");
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [status, setStatus] = useState<"draft" | "active" | "archived">("active");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setName(student?.name ?? "");
    setStudentType(student?.student_type ?? "ug");
    setRoll(student?.roll_number ?? "");
    setRegistration(student?.registration_number ?? "");
    setEnrollment(student?.university_enrollment ?? "");
    setEmail(student?.email ?? "");
    setPhone(student?.phone ?? "");
    setProgramme(student?.programme ?? "");
    setDepartment(student?.department ?? "");
    setSemester(student?.semester != null ? String(student.semester) : "");
    setSection(student?.section ?? "");
    setBatch(student?.batch ?? "");
    setAdmissionDate(student?.admission_date ?? "");
    setGraduation(student?.expected_graduation ?? "");
    setResearchArea(student?.research_area ?? "");
    setOrcid(student?.orcid ?? "");
    setScholar(student?.google_scholar ?? "");
    setNotes(student?.notes ?? "");
    setTags((student?.tags ?? []).join(", "));
    setStatus(student?.status ?? "active");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
    setTimeout(() => firstFieldRef.current?.focus(), 50);
  }, [open, student]);

  if (!open) return null;

  const researchFields = studentType === "phd" || studentType === "alumni";

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);

    const trimmedName = name.trim();
    if (!trimmedName) {
      setFormError("Name must not be empty.");
      return;
    }
    if (!roll.trim()) {
      setFormError("Roll number is required (the institution identity of a student).");
      return;
    }
    const semesterNumber = semester.trim() ? Number(semester.trim()) : null;
    if (semesterNumber != null && (!Number.isInteger(semesterNumber) || semesterNumber < 1 || semesterNumber > 12)) {
      setFormError("Semester must be a number between 1 and 12.");
      return;
    }

    const payload = {
      name: trimmedName,
      student_type: studentType,
      uploaded_by: uploadedBy.trim() || "system",
      status,
      roll_number: roll.trim(),
      registration_number: registration.trim() || null,
      university_enrollment: enrollment.trim() || null,
      email: email.trim() || null,
      phone: phone.trim() || null,
      programme: programme.trim() || null,
      department: department.trim() || null,
      semester: semesterNumber,
      section: section.trim() || null,
      batch: batch.trim() || null,
      admission_date: admissionDate.trim() || null,
      expected_graduation: graduation.trim() || null,
      research_area: researchArea.trim() || null,
      orcid: orcid.trim() || null,
      google_scholar: scholar.trim() || null,
      notes: notes.trim() || null,
      tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
    };

    submittingRef.current = true;
    setSubmitting(true);
    try {
      const saved = student
        ? await updateStudent(student.id, payload)
        : await createStudent(payload);
      onSaved({ student: saved, mode });
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
        aria-labelledby="student-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-3xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 id="student-modal-title" className="text-base font-semibold text-[var(--text-primary)]">
            {mode === "edit" ? "Edit Student" : "Admit Student"}
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
            <p
              role="alert"
              className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
            >
              {formError}
            </p>
          ) : null}

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Identity
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Full name">
                <input
                  ref={firstFieldRef}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="Asha Verma"
                  required
                />
              </Field>
              <Field label="Student type">
                <select
                  value={studentType}
                  onChange={(event) => setStudentType(event.target.value as StudentTypeValue)}
                  className={FIELD_CLASS}
                  aria-label="Student type"
                >
                  {STUDENT_TYPES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Roll number" hint="Unique per institution — duplicates are rejected.">
                <input value={roll} onChange={(event) => setRoll(event.target.value)} className={FIELD_CLASS} required />
              </Field>
              <Field label="Registration number">
                <input value={registration} onChange={(event) => setRegistration(event.target.value)} className={FIELD_CLASS} />
              </Field>
              <Field label="University enrollment">
                <input value={enrollment} onChange={(event) => setEnrollment(event.target.value)} className={FIELD_CLASS} />
              </Field>
              <Field label="Batch">
                <input value={batch} onChange={(event) => setBatch(event.target.value)} className={FIELD_CLASS} placeholder="2026-30" />
              </Field>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Contact & programme
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Email">
                <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} className={FIELD_CLASS} />
              </Field>
              <Field label="Phone">
                <input value={phone} onChange={(event) => setPhone(event.target.value)} className={FIELD_CLASS} />
              </Field>
              <Field label="Programme">
                <input value={programme} onChange={(event) => setProgramme(event.target.value)} className={FIELD_CLASS} placeholder="BSc Mathematics with Data Science" />
              </Field>
              <Field label="Department">
                <input value={department} onChange={(event) => setDepartment(event.target.value)} className={FIELD_CLASS} />
              </Field>
              <Field label="Semester">
                <input type="number" min={1} max={12} value={semester} onChange={(event) => setSemester(event.target.value)} className={FIELD_CLASS} />
              </Field>
              <Field label="Section">
                <input value={section} onChange={(event) => setSection(event.target.value)} className={FIELD_CLASS} />
              </Field>
              <Field label="Admission date" hint="YYYY, YYYY-MM or YYYY-MM-DD.">
                <input value={admissionDate} onChange={(event) => setAdmissionDate(event.target.value)} className={FIELD_CLASS} placeholder="2026-07-15" />
              </Field>
              <Field label="Expected graduation">
                <input value={graduation} onChange={(event) => setGraduation(event.target.value)} className={FIELD_CLASS} placeholder="2030-05" />
              </Field>
            </div>
          </fieldset>

          {researchFields ? (
            <fieldset className="space-y-3">
              <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                Research (PhD / Alumni)
              </legend>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field label="Research area">
                  <input value={researchArea} onChange={(event) => setResearchArea(event.target.value)} className={FIELD_CLASS} />
                </Field>
                <Field label="ORCID" hint="0000-0002-1825-0097">
                  <input value={orcid} onChange={(event) => setOrcid(event.target.value)} className={FIELD_CLASS} />
                </Field>
                <Field label="Google Scholar URL">
                  <input type="url" value={scholar} onChange={(event) => setScholar(event.target.value)} className={FIELD_CLASS} />
                </Field>
              </div>
            </fieldset>
          ) : null}

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Notes & administration
            </legend>
            <Field label="Tags" hint="Comma-separated.">
              <input value={tags} onChange={(event) => setTags(event.target.value)} className={FIELD_CLASS} placeholder="hostel, scholarship" />
            </Field>
            <Field label="Notes">
              <textarea value={notes} onChange={(event) => setNotes(event.target.value)} className={FIELD_CLASS} rows={2} />
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Status">
                <select
                  value={status}
                  onChange={(event) => setStatus(event.target.value as "draft" | "active" | "archived")}
                  className={FIELD_CLASS}
                  aria-label="Status"
                >
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
            {mode === "edit" ? "Save changes" : "Admit student"}
          </button>
        </div>
      </form>
    </div>
  );
}

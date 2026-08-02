"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { listObjects } from "@/lib/api/objects";
import { createProject, listAgencies, updateProject } from "@/lib/api/research";
import { listStudents } from "@/lib/api/students";
import {
  PROJECT_LIFECYCLE_STATUSES,
  PROJECT_PRIORITIES,
} from "@/lib/research/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type {
  ObjectResponse,
  ProjectLifecycleStatus,
  ProjectResponse,
  ResearchObjectStatus,
} from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

const MULTI_SELECT_CLASS = `${FIELD_CLASS} h-28`;

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

interface PickerOption {
  id: string;
  label: string;
}

function MultiSelect({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: PickerOption[];
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  return (
    <select
      multiple
      value={selected}
      onChange={(event) =>
        onChange(Array.from(event.target.selectedOptions).map((option) => option.value))
      }
      className={MULTI_SELECT_CLASS}
      aria-label={label}
    >
      {options.map((option) => (
        <option key={option.id} value={option.id}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

export interface ProjectSaveResult {
  project: ProjectResponse;
  mode: "create" | "edit";
}

/**
 * Register / edit a Research Project. Create mode posts the full registry
 * record (identity, lifecycle, budget, links, team); edit mode PUTs the same
 * shape (the backend's per-group merge contract keeps it consistent).
 */
export function ProjectModal({
  open,
  onClose,
  onSaved,
  project,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (result: ProjectSaveResult) => void;
  project?: ProjectResponse | null;
}) {
  const mode = project ? "edit" : "create";
  const [title, setTitle] = useState("");
  const [code, setCode] = useState("");
  const [lifecycle, setLifecycle] = useState<ProjectLifecycleStatus>("draft");
  const [department, setDepartment] = useState("");
  const [grantNumber, setGrantNumber] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [duration, setDuration] = useState("");
  const [budgetApproved, setBudgetApproved] = useState("");
  const [budgetUtilized, setBudgetUtilized] = useState("");
  const [objectives, setObjectives] = useState("");
  const [keywords, setKeywords] = useState("");
  const [abstract, setAbstract] = useState("");
  const [priority, setPriority] = useState("");
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState("");
  const [agencyIds, setAgencyIds] = useState<string[]>([]);
  const [committeeIds, setCommitteeIds] = useState<string[]>([]);
  const [piIds, setPiIds] = useState<string[]>([]);
  const [coPiIds, setCoPiIds] = useState<string[]>([]);
  const [memberIds, setMemberIds] = useState<string[]>([]);
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [status, setStatus] = useState<ResearchObjectStatus>("active");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  // Picker option lists (typed pickers, like PublicationModal's link groups).
  const [agencyOptions, setAgencyOptions] = useState<PickerOption[]>([]);
  const [committeeOptions, setCommitteeOptions] = useState<PickerOption[]>([]);
  const [facultyOptions, setFacultyOptions] = useState<PickerOption[]>([]);
  const [peopleOptions, setPeopleOptions] = useState<PickerOption[]>([]);

  useEffect(() => {
    if (!open) return;
    setTitle(project?.title ?? "");
    setCode(project?.project_code ?? "");
    setLifecycle(project?.lifecycle_status ?? "draft");
    setDepartment(project?.department ?? "");
    setGrantNumber(project?.grant_number ?? "");
    setStartDate(project?.start_date ?? "");
    setEndDate(project?.end_date ?? "");
    setDuration(project?.duration ?? "");
    setBudgetApproved(
      project?.budget_approved != null ? String(project.budget_approved) : "",
    );
    setBudgetUtilized(
      project?.budget_utilized != null ? String(project.budget_utilized) : "",
    );
    setObjectives(project?.objectives ?? "");
    setKeywords((project?.keywords ?? []).join(", "));
    setAbstract(project?.abstract ?? "");
    setPriority(project?.priority ?? "");
    setNotes(project?.notes ?? "");
    setTags((project?.tags ?? []).join(", "));
    setAgencyIds((project?.links?.agencies ?? []).map((link) => link.id));
    setCommitteeIds((project?.links?.committees ?? []).map((link) => link.id));
    setPiIds((project?.team?.principal_investigators ?? []).map((link) => link.id));
    setCoPiIds((project?.team?.co_investigators ?? []).map((link) => link.id));
    setMemberIds((project?.team?.team_members ?? []).map((link) => link.id));
    setStatus(project?.status ?? "active");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
  }, [open, project]);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    listAgencies({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setAgencyOptions(response.items.map((a) => ({ id: a.id, label: a.name }))),
      )
      .catch(() => setAgencyOptions([]));
    listObjects({ pageSize: 100 }, { signal: controller.signal })
      .then((response) => {
        const committees: PickerOption[] = [];
        const faculty: PickerOption[] = [];
        const people: PickerOption[] = [];
        for (const object of response.items as ObjectResponse[]) {
          if (object.object_type === "committee") {
            committees.push({ id: object.id, label: object.title });
          }
          if (object.object_type === "faculty") {
            people.push({ id: object.id, label: object.title });
            faculty.push({ id: object.id, label: object.title });
          }
        }
        setCommitteeOptions(committees);
        setFacultyOptions(faculty);
        setPeopleOptions(people);
      })
      .catch(() => {
        setCommitteeOptions([]);
        setFacultyOptions([]);
        setPeopleOptions([]);
      });
    // Team members may be students too — the student registry feeds the picker.
    listStudents({ pageSize: 100 }, { signal: controller.signal })
      .then((response) => {
        setPeopleOptions((current) => [
          ...current,
          ...response.items.map((student) => ({
            id: student.id,
            label: `${student.name} (student)`,
          })),
        ]);
      })
      .catch(() => undefined);
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

  const parseAmount = (raw: string): number | null => {
    const trimmed = raw.trim();
    if (!trimmed) return null;
    const value = Number(trimmed.replace(/,/g, ""));
    return Number.isFinite(value) ? value : null;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);

    if (!title.trim()) {
      setFormError("Project title must not be empty.");
      return;
    }
    if (startDate.trim() && endDate.trim() && endDate.trim() < startDate.trim()) {
      setFormError("End date must not be before the start date.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);

    const splitList = (raw: string) =>
      raw
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean);

    const payload = {
      title: title.trim(),
      uploaded_by: uploadedBy.trim() || "faculty:ui",
      status,
      lifecycle_status: lifecycle,
      project_code: code.trim() || null,
      department: department.trim() || null,
      grant_number: grantNumber.trim() || null,
      start_date: startDate.trim() || null,
      end_date: endDate.trim() || null,
      duration: duration.trim() || null,
      budget_approved: parseAmount(budgetApproved),
      budget_utilized: parseAmount(budgetUtilized),
      objectives: objectives.trim() || null,
      keywords: splitList(keywords),
      abstract: abstract.trim() || null,
      priority: priority || null,
      notes: notes.trim() || null,
      tags: splitList(tags),
      links: { agencies: agencyIds, committees: committeeIds },
      team: {
        principal_investigators: piIds,
        co_investigators: coPiIds,
        team_members: memberIds,
      },
    };

    try {
      const saved = project
        ? await updateProject(project.id, payload)
        : await createProject(payload);
      submittingRef.current = false;
      setSubmitting(false);
      onSaved({ project: saved, mode });
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
        aria-labelledby="project-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-3xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 id="project-modal-title" className="text-base font-semibold text-[var(--text-primary)]">
            {mode === "edit" ? "Edit research project" : "New research project"}
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
            <Field label="Project title">
              <input
                ref={firstFieldRef}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className={FIELD_CLASS}
                required
              />
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Project code" hint="Unique per institution — duplicates are rejected.">
                <input value={code} onChange={(event) => setCode(event.target.value)} className={FIELD_CLASS} placeholder="DST-2026-0137" />
              </Field>
              <Field label="Department">
                <input value={department} onChange={(event) => setDepartment(event.target.value)} className={FIELD_CLASS} />
              </Field>
              <Field label="Grant number (sanction reference)">
                <input value={grantNumber} onChange={(event) => setGrantNumber(event.target.value)} className={FIELD_CLASS} />
              </Field>
              <Field label="Priority">
                <select
                  value={priority}
                  onChange={(event) => setPriority(event.target.value)}
                  className={FIELD_CLASS}
                  aria-label="Priority"
                >
                  <option value="">—</option>
                  {PROJECT_PRIORITIES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Lifecycle, dates & budget
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Lifecycle status">
                <select
                  value={lifecycle}
                  onChange={(event) => setLifecycle(event.target.value as ProjectLifecycleStatus)}
                  className={FIELD_CLASS}
                  aria-label="Lifecycle status"
                >
                  {PROJECT_LIFECYCLE_STATUSES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Duration" hint='Free text, e.g. "36 months".'>
                <input value={duration} onChange={(event) => setDuration(event.target.value)} className={FIELD_CLASS} />
              </Field>
              <Field label="Start date" hint="YYYY-MM-DD.">
                <input value={startDate} onChange={(event) => setStartDate(event.target.value)} className={FIELD_CLASS} placeholder="2026-04-01" />
              </Field>
              <Field label="End date">
                <input value={endDate} onChange={(event) => setEndDate(event.target.value)} className={FIELD_CLASS} placeholder="2029-03-31" />
              </Field>
              <Field label="Budget approved (₹)">
                <input
                  inputMode="decimal"
                  value={budgetApproved}
                  onChange={(event) => setBudgetApproved(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="4500000"
                />
              </Field>
              <Field label="Budget utilized (₹)">
                <input
                  inputMode="decimal"
                  value={budgetUtilized}
                  onChange={(event) => setBudgetUtilized(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="0"
                />
              </Field>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Research content
            </legend>
            <Field label="Objectives">
              <textarea value={objectives} onChange={(event) => setObjectives(event.target.value)} className={FIELD_CLASS} rows={2} />
            </Field>
            <Field label="Abstract">
              <textarea value={abstract} onChange={(event) => setAbstract(event.target.value)} className={FIELD_CLASS} rows={3} />
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Keywords" hint="Comma-separated.">
                <input value={keywords} onChange={(event) => setKeywords(event.target.value)} className={FIELD_CLASS} placeholder="quantum, materials" />
              </Field>
              <Field label="Tags" hint="Comma-separated.">
                <input value={tags} onChange={(event) => setTags(event.target.value)} className={FIELD_CLASS} placeholder="flagship, seed" />
              </Field>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Funding & governance
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Funding agencies" hint="Ctrl/Cmd-click for multiple;">
                <MultiSelect
                  label="Linked funding agencies"
                  options={agencyOptions}
                  selected={agencyIds}
                  onChange={setAgencyIds}
                />
              </Field>
              <Field label="Committees" hint="Ctrl/Cmd-click for multiple;">
                <MultiSelect
                  label="Linked committees"
                  options={committeeOptions}
                  selected={committeeIds}
                  onChange={setCommitteeIds}
                />
              </Field>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Team
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field label="Principal Investigator">
                <MultiSelect
                  label="Principal investigators"
                  options={facultyOptions}
                  selected={piIds}
                  onChange={setPiIds}
                />
              </Field>
              <Field label="Co-PI(s)">
                <MultiSelect
                  label="Co-investigators"
                  options={facultyOptions}
                  selected={coPiIds}
                  onChange={setCoPiIds}
                />
              </Field>
              <Field label="Research team" hint="Faculty and students;">
                <MultiSelect
                  label="Research team members"
                  options={peopleOptions}
                  selected={memberIds}
                  onChange={setMemberIds}
                />
              </Field>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Notes & administration
            </legend>
            <Field label="Notes">
              <textarea value={notes} onChange={(event) => setNotes(event.target.value)} className={FIELD_CLASS} rows={2} />
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Status">
                <select
                  value={status}
                  onChange={(event) => setStatus(event.target.value as ResearchObjectStatus)}
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
            {mode === "edit" ? "Save changes" : "Register project"}
          </button>
        </div>
      </form>
    </div>
  );
}

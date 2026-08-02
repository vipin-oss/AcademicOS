"use client";

import { useEffect, useRef, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { createCommittee, updateCommittee } from "@/lib/api/committees";
import type { CommitteeMemberPayload } from "@/lib/api/committees";
import { listFaculty } from "@/lib/api/faculty";
import { listGrants, listProjects } from "@/lib/api/research";
import { listStudents } from "@/lib/api/students";
import { listPublications } from "@/lib/api/publications";
import { COMMITTEE_ROLES, COMMITTEE_TYPES } from "@/lib/committees/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type {
  CommitteeLinkGroup,
  CommitteeResponse,
  CommitteeRole,
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

/** One editable member row (person + PART 2 role + tenure). */
interface MemberRow {
  id: string;
  role: CommitteeRole;
  start_date: string;
  end_date: string;
  remarks: string;
}

export interface CommitteeSaveResult {
  committee: CommitteeResponse;
  mode: "create" | "edit";
}

/**
 * Register / edit a Committee. Create mode posts the full registry record
 * (PART 1 identity + PART 2 members + PART 7 research links); edit mode PUTs
 * the same shape (the backend's per-group replace contract keeps it consistent).
 */
export function CommitteeModal({
  open,
  onClose,
  onSaved,
  committee,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (result: CommitteeSaveResult) => void;
  committee?: CommitteeResponse | null;
}) {
  const mode = committee ? "edit" : "create";
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [committeeType, setCommitteeType] = useState("");
  const [department, setDepartment] = useState("");
  const [school, setSchool] = useState("");
  const [description, setDescription] = useState("");
  const [constitutionDate, setConstitutionDate] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState("");
  const [members, setMembers] = useState<MemberRow[]>([]);
  const [projectIds, setProjectIds] = useState<string[]>([]);
  const [grantIds, setGrantIds] = useState<string[]>([]);
  const [studentIds, setStudentIds] = useState<string[]>([]);
  const [publicationIds, setPublicationIds] = useState<string[]>([]);
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [status, setStatus] = useState<ResearchObjectStatus>("active");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  // Picker option lists (typed pickers, like ProjectModal's link groups).
  const [peopleOptions, setPeopleOptions] = useState<PickerOption[]>([]);
  const [projectOptions, setProjectOptions] = useState<PickerOption[]>([]);
  const [grantOptions, setGrantOptions] = useState<PickerOption[]>([]);
  const [studentOptions, setStudentOptions] = useState<PickerOption[]>([]);
  const [publicationOptions, setPublicationOptions] = useState<PickerOption[]>([]);

  useEffect(() => {
    if (!open) return;
    setName(committee?.name ?? "");
    setCode(committee?.committee_code ?? "");
    setCommitteeType(committee?.committee_type ?? "");
    setDepartment(committee?.department ?? "");
    setSchool(committee?.school ?? "");
    setDescription(committee?.description ?? "");
    setConstitutionDate(committee?.constitution_date ?? "");
    setExpiryDate(committee?.expiry_date ?? "");
    setNotes(committee?.notes ?? "");
    setTags((committee?.tags ?? []).join(", "));
    setMembers(
      (committee?.members ?? []).map((member) => ({
        id: member.id,
        role: member.role,
        start_date: member.start_date ?? "",
        end_date: member.end_date ?? "",
        remarks: member.remarks ?? "",
      })),
    );
    setProjectIds((committee?.links?.projects ?? []).map((link) => link.id));
    setGrantIds((committee?.links?.grants ?? []).map((link) => link.id));
    setStudentIds((committee?.links?.students ?? []).map((link) => link.id));
    setPublicationIds((committee?.links?.publications ?? []).map((link) => link.id));
    setStatus(committee?.status ?? "active");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
  }, [open, committee]);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    // Members are faculty and/or students (PART 2 reuses the Faculty module).
    // Both registries are fetched and set ONCE — independent fetches would
    // race and the slower response would clobber the faster one's options.
    Promise.all([
      listFaculty({ pageSize: 100 }, { signal: controller.signal }).catch(() => null),
      listStudents({ pageSize: 100 }, { signal: controller.signal }).catch(() => null),
    ])
      .then(([facultyRes, studentRes]) => {
        const people: PickerOption[] = [];
        if (facultyRes) {
          people.push(
            ...facultyRes.items.map((person) => ({ id: person.id, label: person.name })),
          );
        }
        if (studentRes) {
          const options = studentRes.items.map((student) => ({
            id: student.id,
            label: `${student.name} (student)`,
          }));
          people.push(...options);
          setStudentOptions(options);
        } else {
          setStudentOptions([]);
        }
        setPeopleOptions(people);
      })
      .catch(() => setPeopleOptions([]));
    listProjects({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setProjectOptions(response.items.map((project) => ({ id: project.id, label: project.title }))),
      )
      .catch(() => setProjectOptions([]));
    listGrants({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setGrantOptions(response.items.map((grant) => ({ id: grant.id, label: grant.title }))),
      )
      .catch(() => setGrantOptions([]));
    listPublications({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setPublicationOptions(
          response.items.map((publication) => ({
            id: publication.id,
            label: publication.title,
          })),
        ),
      )
      .catch(() => setPublicationOptions([]));
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

  const addMemberRow = () =>
    setMembers((rows) => [
      ...rows,
      { id: "", role: "member", start_date: "", end_date: "", remarks: "" },
    ]);

  const removeMemberRow = (index: number) =>
    setMembers((rows) => rows.filter((_, rowIndex) => rowIndex !== index));

  const patchMemberRow = (index: number, patch: Partial<MemberRow>) =>
    setMembers((rows) =>
      rows.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);

    if (!name.trim()) {
      setFormError("Committee name must not be empty.");
      return;
    }
    if (constitutionDate.trim() && expiryDate.trim() && expiryDate.trim() < constitutionDate.trim()) {
      setFormError("Expiry date must not be before the constitution date.");
      return;
    }
    const filledMembers = members.filter((row) => row.id || row.remarks.trim());
    const incomplete = filledMembers.find((row) => !row.id);
    if (incomplete) {
      setFormError("Every member row needs a person selected (or remove the row).");
      return;
    }
    const seen = new Set<string>();
    for (const row of filledMembers) {
      if (seen.has(row.id)) {
        setFormError("The same person is listed twice — combine the roles into one row each.");
        return;
      }
      seen.add(row.id);
    }

    submittingRef.current = true;
    setSubmitting(true);

    const splitList = (raw: string) =>
      raw
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean);

    const memberPayload: CommitteeMemberPayload[] = members
      .filter((row) => row.id)
      .map((row) => ({
        faculty_id: row.id,
        role: row.role,
        start_date: row.start_date.trim() || null,
        end_date: row.end_date.trim() || null,
        remarks: row.remarks.trim() || null,
      }));

    const payload = {
      name: name.trim(),
      uploaded_by: uploadedBy.trim() || "faculty:ui",
      status,
      committee_code: code.trim() || null,
      committee_type: committeeType || null,
      department: department.trim() || null,
      school: school.trim() || null,
      description: description.trim() || null,
      constitution_date: constitutionDate.trim() || null,
      expiry_date: expiryDate.trim() || null,
      notes: notes.trim() || null,
      tags: splitList(tags),
      members: memberPayload,
      links: {
        projects: projectIds,
        grants: grantIds,
        students: studentIds,
        publications: publicationIds,
      } as Partial<Record<CommitteeLinkGroup, string[]>>,
    };

    try {
      const saved = committee
        ? await updateCommittee(committee.id, payload)
        : await createCommittee(payload);
      submittingRef.current = false;
      setSubmitting(false);
      onSaved({ committee: saved, mode });
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
        aria-labelledby="committee-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-3xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="committee-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            {mode === "edit" ? "Edit committee" : "New committee"}
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
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Committee name *">
              <input
                ref={firstFieldRef}
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Central Purchase Committee"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Committee code" hint="Unique when provided (409 on duplicates).">
              <input
                type="text"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="e.g. CPC-2026"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Committee type">
              <select
                value={committeeType}
                onChange={(event) => setCommitteeType(event.target.value)}
                className={FIELD_CLASS}
              >
                <option value="">— Select type —</option>
                {COMMITTEE_TYPES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Status">
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value as ResearchObjectStatus)}
                className={FIELD_CLASS}
              >
                <option value="active">Active</option>
                <option value="draft">Draft</option>
                <option value="archived">Archived</option>
              </select>
            </Field>
            <Field label="Department">
              <input
                type="text"
                value={department}
                onChange={(event) => setDepartment(event.target.value)}
                placeholder="e.g. Computer Science"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="School">
              <input
                type="text"
                value={school}
                onChange={(event) => setSchool(event.target.value)}
                placeholder="e.g. School of Engineering"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Constitution date">
              <input
                type="date"
                value={constitutionDate}
                onChange={(event) => setConstitutionDate(event.target.value)}
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Expiry date">
              <input
                type="date"
                value={expiryDate}
                onChange={(event) => setExpiryDate(event.target.value)}
                className={FIELD_CLASS}
              />
            </Field>
          </div>

          <Field label="Description">
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={2}
              placeholder="Mandate, scope and quorum rules…"
              className={FIELD_CLASS}
            />
          </Field>

          {/* PART 2 members editor */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-medium text-[var(--text-secondary)]">
                Members (faculty / students)
              </span>
              <button
                type="button"
                onClick={addMemberRow}
                className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add member
              </button>
            </div>
            {members.length === 0 ? (
              <p className="rounded-lg border border-dashed border-[var(--border-strong)] px-3 py-3 text-xs text-[var(--text-tertiary)]">
                No members yet — add the chairperson, convener and members.
              </p>
            ) : (
              <ul className="space-y-2">
                {members.map((row, index) => (
                  <li
                    key={index}
                    className="grid grid-cols-1 items-end gap-2 rounded-lg border border-[var(--border-subtle)] p-2 sm:grid-cols-[1fr_130px_130px_130px_1fr_auto]"
                  >
                    <label className="block">
                      <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                        Person
                      </span>
                      <select
                        value={row.id}
                        onChange={(event) => patchMemberRow(index, { id: event.target.value })}
                        aria-label={`Member ${index + 1} person`}
                        className={FIELD_CLASS}
                      >
                        <option value="">— Select person —</option>
                        {peopleOptions.map((option) => (
                          <option key={option.id} value={option.id}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                        Role
                      </span>
                      <select
                        value={row.role}
                        onChange={(event) =>
                          patchMemberRow(index, { role: event.target.value as CommitteeRole })
                        }
                        aria-label={`Member ${index + 1} role`}
                        className={FIELD_CLASS}
                      >
                        {COMMITTEE_ROLES.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                        Start date
                      </span>
                      <input
                        type="date"
                        value={row.start_date}
                        onChange={(event) =>
                          patchMemberRow(index, { start_date: event.target.value })
                        }
                        aria-label={`Member ${index + 1} start date`}
                        className={FIELD_CLASS}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                        End date
                      </span>
                      <input
                        type="date"
                        value={row.end_date}
                        onChange={(event) =>
                          patchMemberRow(index, { end_date: event.target.value })
                        }
                        aria-label={`Member ${index + 1} end date`}
                        className={FIELD_CLASS}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                        Remarks
                      </span>
                      <input
                        type="text"
                        value={row.remarks}
                        onChange={(event) =>
                          patchMemberRow(index, { remarks: event.target.value })
                        }
                        aria-label={`Member ${index + 1} remarks`}
                        placeholder="Optional"
                        className={FIELD_CLASS}
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => removeMemberRow(index)}
                      aria-label={`Remove member ${index + 1}`}
                      className="rounded-lg p-2 text-[var(--danger)] transition-colors hover:bg-[var(--danger-subtle)]"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* PART 7 research links */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Linked research projects">
              <MultiSelect
                label="Linked research projects"
                options={projectOptions}
                selected={projectIds}
                onChange={setProjectIds}
              />
            </Field>
            <Field label="Linked grants">
              <MultiSelect
                label="Linked grants"
                options={grantOptions}
                selected={grantIds}
                onChange={setGrantIds}
              />
            </Field>
            <Field label="Linked students">
              <MultiSelect
                label="Linked students"
                options={studentOptions}
                selected={studentIds}
                onChange={setStudentIds}
              />
            </Field>
            <Field label="Linked publications">
              <MultiSelect
                label="Linked publications"
                options={publicationOptions}
                selected={publicationIds}
                onChange={setPublicationIds}
              />
            </Field>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Notes">
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                rows={2}
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Tags" hint="Comma-separated.">
              <input
                type="text"
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                placeholder="governance, 2026"
                className={FIELD_CLASS}
              />
            </Field>
          </div>

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
                : "Create committee"}
          </button>
        </div>
      </form>
    </div>
  );
}

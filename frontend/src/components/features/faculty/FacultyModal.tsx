"use client";

import { useEffect, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { listObjects } from "@/lib/api/objects";
import { createFaculty, updateFaculty } from "@/lib/api/faculty";
import {
  DESIGNATIONS,
  EMPLOYMENT_TYPES,
  PROFILE_SECTIONS,
  type ProfileSectionConfig,
} from "@/lib/faculty/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type {
  FacultyEmploymentType,
  FacultyResponse,
  FacultySectionEntry,
  ObjectResponse,
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

type SectionRows = Record<ProfileSectionConfig["key"], FacultySectionEntry[]>;

function emptySections(): SectionRows {
  return {
    degrees: [],
    experience: [],
    awards: [],
    memberships: [],
    certifications: [],
    admin_positions: [],
  };
}

/** Drop rows that carry no text at all and trim every value before saving. */
function cleanRows(rows: FacultySectionEntry[]): FacultySectionEntry[] {
  return rows
    .map((row) =>
      Object.fromEntries(
        Object.entries(row)
          .map(([key, value]) => [key, String(value ?? "").trim()])
          .filter(([, value]) => value !== ""),
      ),
    )
    .filter((row) => Object.keys(row).length > 0);
}

/** PART 2 rows editor for one profile section ({degree, institution, year}…). */
function ProfileSectionEditor({
  config,
  rows,
  onChange,
}: {
  config: ProfileSectionConfig;
  rows: FacultySectionEntry[];
  onChange: (rows: FacultySectionEntry[]) => void;
}) {
  const updateCell = (index: number, key: string, value: string) => {
    onChange(rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
  };
  const removeRow = (index: number) => {
    onChange(rows.filter((_, i) => i !== index));
  };
  const addRow = () => {
    onChange([...rows, {}]);
  };
  return (
    <fieldset className="space-y-2">
      <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
        {config.label}
      </legend>
      {rows.map((row, index) => (
        <div key={index} className="flex items-start gap-2">
          <div
            className="grid flex-1 grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3"
            data-section={config.key}
          >
            {config.fields.map((field) => (
              <input
                key={field.key}
                value={row[field.key] ?? ""}
                onChange={(event) => updateCell(index, field.key, event.target.value)}
                placeholder={field.placeholder ?? field.label}
                aria-label={`${config.label} row ${index + 1} ${field.label}`}
                className={FIELD_CLASS}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={() => removeRow(index)}
            aria-label={`Remove ${config.label} row ${index + 1}`}
            title="Remove row"
            className="mt-1.5 rounded-lg p-1.5 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={addRow}
        className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
      >
        <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add {config.label.toLowerCase()}
      </button>
    </fieldset>
  );
}

export interface FacultySaveResult {
  faculty: FacultyResponse;
  mode: "create" | "edit";
}

/**
 * Add / edit a Faculty member. Create mode posts the full directory record
 * (identity, contact, scholar identifiers, profile sections, committees);
 * edit mode PUTs the same shape (the backend's merge contract: provided
 * keys replace verbatim, absent keys are untouched).
 */
export function FacultyModal({
  open,
  onClose,
  onSaved,
  faculty,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (result: FacultySaveResult) => void;
  faculty?: FacultyResponse | null;
}) {
  const mode = faculty ? "edit" : "create";
  const [name, setName] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [facultyCode, setFacultyCode] = useState("");
  const [designation, setDesignation] = useState("");
  const [department, setDepartment] = useState("");
  const [school, setSchool] = useState("");
  const [joiningDate, setJoiningDate] = useState("");
  const [employmentType, setEmploymentType] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [office, setOffice] = useState("");
  const [qualification, setQualification] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [researchInterests, setResearchInterests] = useState("");
  const [biography, setBiography] = useState("");
  const [orcid, setOrcid] = useState("");
  const [scopusId, setScopusId] = useState("");
  const [googleScholar, setGoogleScholar] = useState("");
  const [researchgate, setResearchgate] = useState("");
  const [website, setWebsite] = useState("");
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState("");
  const [sections, setSections] = useState<SectionRows>(emptySections);
  const [committeeIds, setCommitteeIds] = useState<string[]>([]);
  const [committeeOptions, setCommitteeOptions] = useState<PickerOption[]>([]);
  const [uploadedBy, setUploadedBy] = useState("registrar:ui");
  const [status, setStatus] = useState<ResearchObjectStatus>("active");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setName(faculty?.name ?? "");
    setEmployeeId(faculty?.employee_id ?? "");
    setFacultyCode(faculty?.faculty_code ?? "");
    setDesignation(faculty?.designation ?? "");
    setDepartment(faculty?.department ?? "");
    setSchool(faculty?.school ?? "");
    setJoiningDate(faculty?.joining_date ?? "");
    setEmploymentType(faculty?.employment_type ?? "");
    setEmail(faculty?.email ?? "");
    setMobile(faculty?.mobile ?? "");
    setOffice(faculty?.office ?? "");
    setQualification(faculty?.qualification ?? "");
    setSpecialization(faculty?.specialization ?? "");
    setResearchInterests((faculty?.research_interests ?? []).join(", "));
    setBiography(faculty?.biography ?? "");
    setOrcid(faculty?.orcid ?? "");
    setScopusId(faculty?.scopus_id ?? "");
    setGoogleScholar(faculty?.google_scholar ?? "");
    setResearchgate(faculty?.researchgate ?? "");
    setWebsite(faculty?.website ?? "");
    setNotes(faculty?.notes ?? "");
    setTags((faculty?.tags ?? []).join(", "));
    setSections({
      degrees: faculty?.degrees ?? [],
      experience: faculty?.experience ?? [],
      awards: faculty?.awards ?? [],
      memberships: faculty?.memberships ?? [],
      certifications: faculty?.certifications ?? [],
      admin_positions: faculty?.admin_positions ?? [],
    });
    setCommitteeIds((faculty?.links?.committees ?? []).map((link) => link.id));
    setStatus(faculty?.status ?? "active");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
  }, [open, faculty]);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    listObjects({ pageSize: 100 }, { signal: controller.signal })
      .then((response) => {
        const committees: PickerOption[] = [];
        for (const object of response.items as ObjectResponse[]) {
          if (object.object_type === "committee") {
            committees.push({ id: object.id, label: object.title });
          }
        }
        setCommitteeOptions(committees);
      })
      .catch(() => setCommitteeOptions([]));
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

    if (!name.trim()) {
      setFormError("Faculty name must not be empty.");
      return;
    }
    if (!employeeId.trim()) {
      setFormError("Employee ID is required — it is the institution identity of a faculty member.");
      return;
    }
    if (email.trim() && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setFormError("Email address does not look valid.");
      return;
    }
    if (orcid.trim() && !/^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/.test(orcid.trim())) {
      setFormError("ORCID must look like 0000-0002-1825-0097.");
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
      name: name.trim(),
      employee_id: employeeId.trim(),
      uploaded_by: uploadedBy.trim() || "registrar:ui",
      status,
      faculty_code: facultyCode.trim() || null,
      designation: designation.trim() || null,
      department: department.trim() || null,
      school: school.trim() || null,
      joining_date: joiningDate.trim() || null,
      employment_type: (employmentType || null) as FacultyEmploymentType | null,
      email: email.trim() || null,
      mobile: mobile.trim() || null,
      office: office.trim() || null,
      qualification: qualification.trim() || null,
      specialization: specialization.trim() || null,
      research_interests: splitList(researchInterests),
      biography: biography.trim() || null,
      orcid: orcid.trim() || null,
      scopus_id: scopusId.trim() || null,
      google_scholar: googleScholar.trim() || null,
      researchgate: researchgate.trim() || null,
      website: website.trim() || null,
      notes: notes.trim() || null,
      tags: splitList(tags),
      degrees: cleanRows(sections.degrees),
      experience: cleanRows(sections.experience),
      awards: cleanRows(sections.awards),
      memberships: cleanRows(sections.memberships),
      certifications: cleanRows(sections.certifications),
      admin_positions: cleanRows(sections.admin_positions),
      links: { committees: committeeIds },
    };

    try {
      const saved = faculty
        ? await updateFaculty(faculty.id, payload)
        : await createFaculty(payload);
      submittingRef.current = false;
      setSubmitting(false);
      onSaved({ faculty: saved, mode });
    } catch (err) {
      submittingRef.current = false;
      setSubmitting(false);
      setFormError(toErrorMessage(err));
    }
  };

  const setSectionRows = (key: ProfileSectionConfig["key"]) => {
    return (rows: FacultySectionEntry[]) => {
      setSections((current) => ({ ...current, [key]: rows }));
    };
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
        aria-labelledby="faculty-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-3xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 id="faculty-modal-title" className="text-base font-semibold text-[var(--text-primary)]">
            {mode === "edit" ? "Edit faculty member" : "New faculty member"}
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
            <Field label="Full name">
              <input
                ref={firstFieldRef}
                value={name}
                onChange={(event) => setName(event.target.value)}
                className={FIELD_CLASS}
                placeholder="Dr. Asha Nair"
                required
              />
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Employee ID" hint="Unique per institution — duplicates are rejected (409).">
                <input
                  value={employeeId}
                  onChange={(event) => setEmployeeId(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="EMP-1001"
                  required
                />
              </Field>
              <Field label="Faculty code" hint="Unique when provided (e.g. department roll code).">
                <input
                  value={facultyCode}
                  onChange={(event) => setFacultyCode(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="PHY-A-07"
                />
              </Field>
              <Field label="Designation">
                <input
                  value={designation}
                  onChange={(event) => setDesignation(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="Associate Professor"
                  list="faculty-designations"
                />
                <datalist id="faculty-designations">
                  {DESIGNATIONS.map((item) => (
                    <option key={item} value={item} />
                  ))}
                </datalist>
              </Field>
              <Field label="Department">
                <input
                  value={department}
                  onChange={(event) => setDepartment(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="Physics"
                />
              </Field>
              <Field label="School">
                <input
                  value={school}
                  onChange={(event) => setSchool(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="School of Physical Sciences"
                />
              </Field>
              <Field label="Joining date" hint="YYYY-MM-DD.">
                <input
                  value={joiningDate}
                  onChange={(event) => setJoiningDate(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="2015-07-01"
                />
              </Field>
              <Field label="Employment type">
                <select
                  value={employmentType}
                  onChange={(event) => setEmploymentType(event.target.value)}
                  className={FIELD_CLASS}
                  aria-label="Employment type"
                >
                  <option value="">—</option>
                  {EMPLOYMENT_TYPES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Office">
                <input
                  value={office}
                  onChange={(event) => setOffice(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="B-204"
                />
              </Field>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Contact & academic identity
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Email">
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="asha.nair@univ.edu"
                />
              </Field>
              <Field label="Mobile">
                <input
                  value={mobile}
                  onChange={(event) => setMobile(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="+91-98xxxxxxx1"
                />
              </Field>
              <Field label="Qualification" hint='e.g. "Ph.D. (Physics), IIT Delhi".'>
                <input
                  value={qualification}
                  onChange={(event) => setQualification(event.target.value)}
                  className={FIELD_CLASS}
                />
              </Field>
              <Field label="Specialization">
                <input
                  value={specialization}
                  onChange={(event) => setSpecialization(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="Condensed Matter Physics"
                />
              </Field>
            </div>
            <Field label="Research interests" hint="Comma-separated.">
              <input
                value={researchInterests}
                onChange={(event) => setResearchInterests(event.target.value)}
                className={FIELD_CLASS}
                placeholder="perovskites, quantum dots"
              />
            </Field>
            <Field label="Biography">
              <textarea
                value={biography}
                onChange={(event) => setBiography(event.target.value)}
                className={FIELD_CLASS}
                rows={3}
              />
            </Field>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Scholar identifiers & links
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="ORCID" hint="0000-0002-1825-0097.">
                <input
                  value={orcid}
                  onChange={(event) => setOrcid(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="0000-0002-1825-0097"
                />
              </Field>
              <Field label="Scopus ID">
                <input
                  value={scopusId}
                  onChange={(event) => setScopusId(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="55512345600"
                />
              </Field>
              <Field label="Google Scholar" hint="Profile id or URL.">
                <input
                  value={googleScholar}
                  onChange={(event) => setGoogleScholar(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="abcXYZ"
                />
              </Field>
              <Field label="ResearchGate" hint="Profile slug or URL.">
                <input
                  value={researchgate}
                  onChange={(event) => setResearchgate(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="Asha-Nair-42"
                />
              </Field>
              <Field label="Website" hint="https://…">
                <input
                  value={website}
                  onChange={(event) => setWebsite(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="https://univ.edu/faculty/asha"
                />
              </Field>
            </div>
          </fieldset>

          {PROFILE_SECTIONS.map((section) => (
            <ProfileSectionEditor
              key={section.key}
              config={section}
              rows={sections[section.key]}
              onChange={setSectionRows(section.key)}
            />
          ))}

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Governance
            </legend>
            <Field label="Committee memberships" hint="Ctrl/Cmd-click for multiple;">
              <MultiSelect
                label="Committee memberships"
                options={committeeOptions}
                selected={committeeIds}
                onChange={setCommitteeIds}
              />
            </Field>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Notes & administration
            </legend>
            <Field label="Notes">
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                className={FIELD_CLASS}
                rows={2}
              />
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field label="Tags" hint="Comma-separated.">
                <input
                  value={tags}
                  onChange={(event) => setTags(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="senate, iqac"
                />
              </Field>
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
                <input
                  value={uploadedBy}
                  onChange={(event) => setUploadedBy(event.target.value)}
                  className={FIELD_CLASS}
                />
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
            {mode === "edit" ? "Save changes" : "Add faculty member"}
          </button>
        </div>
      </form>
    </div>
  );
}

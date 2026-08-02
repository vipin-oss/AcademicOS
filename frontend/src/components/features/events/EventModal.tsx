"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { createEvent, updateEvent } from "@/lib/api/events";
import type { CreateEventPayload } from "@/lib/api/events";
import { listFaculty } from "@/lib/api/faculty";
import { listStudents } from "@/lib/api/students";
import { listGrants, listProjects } from "@/lib/api/research";
import { listCommittees } from "@/lib/api/committees";
import {
  EVENT_MODES,
  EVENT_PRIORITIES,
  EVENT_STATUSES,
  EVENT_TYPES,
} from "@/lib/events/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type {
  EventInputLinkGroup,
  EventMode,
  EventPriority,
  EventResponse,
  EventStatus,
  EventType,
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

export interface EventSaveResult {
  event: EventResponse;
  mode: "create" | "edit";
}

/**
 * Register / edit an Event (PART 1 record + PART 5 registration counters +
 * people/research/governance links). Participation, speakers, schedule and
 * linked publications are maintained on the workspace sections after the
 * record exists (same contract as proposal sections).
 */
export function EventModal({
  open,
  onClose,
  onSaved,
  event,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (result: EventSaveResult) => void;
  event?: EventResponse | null;
}) {
  const mode = event ? "edit" : "create";
  const [title, setTitle] = useState("");
  const [eventCode, setEventCode] = useState("");
  const [eventType, setEventType] = useState<EventType>("custom");
  const [organizer, setOrganizer] = useState("");
  const [coOrganizer, setCoOrganizer] = useState("");
  const [venue, setVenue] = useState("");
  const [eventMode, setEventMode] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [department, setDepartment] = useState("");
  const [school, setSchool] = useState("");
  const [description, setDescription] = useState("");
  const [objectives, setObjectives] = useState("");
  const [outcome, setOutcome] = useState("");
  const [eventStatus, setEventStatus] = useState<EventStatus>("planned");
  const [priority, setPriority] = useState("");
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState("");
  const [expected, setExpected] = useState("");
  const [registered, setRegistered] = useState("");
  const [present, setPresent] = useState("");
  const [certificatesIssued, setCertificatesIssued] = useState("");
  const [facultyIds, setFacultyIds] = useState<string[]>([]);
  const [studentIds, setStudentIds] = useState<string[]>([]);
  const [projectIds, setProjectIds] = useState<string[]>([]);
  const [grantIds, setGrantIds] = useState<string[]>([]);
  const [committeeIds, setCommitteeIds] = useState<string[]>([]);
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [status, setStatus] = useState<ResearchObjectStatus>("active");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  // Picker option lists (typed pickers, like ProposalModal's link groups).
  const [facultyOptions, setFacultyOptions] = useState<PickerOption[]>([]);
  const [studentOptions, setStudentOptions] = useState<PickerOption[]>([]);
  const [projectOptions, setProjectOptions] = useState<PickerOption[]>([]);
  const [grantOptions, setGrantOptions] = useState<PickerOption[]>([]);
  const [committeeOptions, setCommitteeOptions] = useState<PickerOption[]>([]);

  useEffect(() => {
    if (!open) return;
    setTitle(event?.title ?? "");
    setEventCode(event?.event_code ?? "");
    setEventType(event?.event_type ?? "custom");
    setOrganizer(event?.organizer ?? "");
    setCoOrganizer(event?.co_organizer ?? "");
    setVenue(event?.venue ?? "");
    setEventMode(event?.mode ?? "");
    setStartDate(event?.start_date ?? "");
    setEndDate(event?.end_date ?? "");
    setDepartment(event?.department ?? "");
    setSchool(event?.school ?? "");
    setDescription(event?.description ?? "");
    setObjectives(event?.objectives ?? "");
    setOutcome(event?.outcome ?? "");
    setEventStatus(event?.event_status ?? "planned");
    setPriority(event?.priority ?? "");
    setNotes(event?.notes ?? "");
    setTags((event?.tags ?? []).join(", "));
    setExpected(String(event?.registration?.expected_participants ?? ""));
    setRegistered(String(event?.registration?.registered ?? ""));
    setPresent(String(event?.registration?.present ?? ""));
    setCertificatesIssued(String(event?.registration?.certificates_issued ?? ""));
    setFacultyIds((event?.links?.faculty ?? []).map((link) => link.id));
    setStudentIds((event?.links?.students ?? []).map((link) => link.id));
    setProjectIds((event?.links?.projects ?? []).map((link) => link.id));
    setGrantIds((event?.links?.grants ?? []).map((link) => link.id));
    setCommitteeIds((event?.links?.committees ?? []).map((link) => link.id));
    setUploadedBy(event?.uploaded_by ?? "faculty:ui");
    setStatus(event?.status ?? "active");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
  }, [open, event]);

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
    listStudents({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setStudentOptions(
          response.items.map((student) => ({ id: student.id, label: student.name })),
        ),
      )
      .catch(() => setStudentOptions([]));
    listProjects({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setProjectOptions(
          response.items.map((project) => ({ id: project.id, label: project.title })),
        ),
      )
      .catch(() => setProjectOptions([]));
    listGrants({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setGrantOptions(response.items.map((grant) => ({ id: grant.id, label: grant.title }))),
      )
      .catch(() => setGrantOptions([]));
    listCommittees({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setCommitteeOptions(
          response.items.map((committee) => ({ id: committee.id, label: committee.name })),
        ),
      )
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

  const counterValue = (raw: string, label: string): number => {
    const trimmed = raw.trim();
    if (!trimmed) return 0;
    const parsed = Number(trimmed);
    if (!Number.isInteger(parsed) || parsed < 0) {
      setFormError(`${label} must be a non-negative whole number.`);
      return Number.NaN;
    }
    return parsed;
  };

  const handleSubmit = async (formEvent: React.FormEvent) => {
    formEvent.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);

    if (!title.trim()) {
      setFormError("Event title must not be empty.");
      return;
    }
    if (startDate && endDate && endDate < startDate) {
      setFormError("End date must not be before the start date.");
      return;
    }
    const counters = {
      expected_participants: counterValue(expected, "Expected participants"),
      registered: counterValue(registered, "Registered"),
      present: counterValue(present, "Present"),
      certificates_issued: counterValue(certificatesIssued, "Certificates issued"),
    };
    if (Object.values(counters).some((value) => Number.isNaN(value))) return;

    submittingRef.current = true;
    setSubmitting(true);

    const splitList = (raw: string) =>
      raw
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean);

    const payload: CreateEventPayload = {
      title: title.trim(),
      uploaded_by: uploadedBy.trim() || "faculty:ui",
      status,
      event_code: eventCode.trim() || null,
      event_type: eventType,
      organizer: organizer.trim() || null,
      co_organizer: coOrganizer.trim() || null,
      venue: venue.trim() || null,
      mode: (eventMode || null) as EventMode | null,
      start_date: startDate.trim() || null,
      end_date: endDate.trim() || null,
      department: department.trim() || null,
      school: school.trim() || null,
      description: description.trim() || null,
      objectives: objectives.trim() || null,
      outcome: outcome.trim() || null,
      event_status: eventStatus,
      priority: (priority || null) as EventPriority | null,
      notes: notes.trim() || null,
      tags: splitList(tags),
      registration: counters,
      links: {
        faculty: facultyIds,
        students: studentIds,
        projects: projectIds,
        grants: grantIds,
        committees: committeeIds,
      } as Partial<Record<EventInputLinkGroup, string[]>>,
    };

    try {
      const saved = event
        ? await updateEvent(event.id, payload)
        : await createEvent(payload);
      submittingRef.current = false;
      setSubmitting(false);
      onSaved({ event: saved, mode });
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
        aria-labelledby="event-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-3xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="event-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            {mode === "edit" ? "Edit event" : "New event"}
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
            <Field label="Event title *">
              <input
                ref={firstFieldRef}
                type="text"
                value={title}
                onChange={(change) => setTitle(change.target.value)}
                aria-label="Event title"
                className={FIELD_CLASS}
                placeholder="e.g. National Mathematics Day 2026"
              />
            </Field>
            <Field label="Event code" hint="Unique when provided (e.g. EVT-2026-001).">
              <input
                type="text"
                value={eventCode}
                onChange={(change) => setEventCode(change.target.value)}
                aria-label="Event code"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Event type">
              <select
                value={eventType}
                onChange={(change) => setEventType(change.target.value as EventType)}
                aria-label="Event type"
                className={FIELD_CLASS}
              >
                {EVENT_TYPES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Status">
              <select
                value={eventStatus}
                onChange={(change) => setEventStatus(change.target.value as EventStatus)}
                aria-label="Event status"
                className={FIELD_CLASS}
              >
                {EVENT_STATUSES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Organizer">
              <input
                type="text"
                value={organizer}
                onChange={(change) => setOrganizer(change.target.value)}
                aria-label="Organizer"
                className={FIELD_CLASS}
                placeholder="e.g. Dept. of Mathematics"
              />
            </Field>
            <Field label="Co-organizer">
              <input
                type="text"
                value={coOrganizer}
                onChange={(change) => setCoOrganizer(change.target.value)}
                aria-label="Co-organizer"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Venue">
              <input
                type="text"
                value={venue}
                onChange={(change) => setVenue(change.target.value)}
                aria-label="Venue"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Mode">
              <select
                value={eventMode}
                onChange={(change) => setEventMode(change.target.value)}
                aria-label="Mode"
                className={FIELD_CLASS}
              >
                <option value="">— Select mode —</option>
                {EVENT_MODES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Start date">
              <input
                type="date"
                value={startDate}
                onChange={(change) => setStartDate(change.target.value)}
                aria-label="Start date"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="End date">
              <input
                type="date"
                value={endDate}
                onChange={(change) => setEndDate(change.target.value)}
                aria-label="End date"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Department">
              <input
                type="text"
                value={department}
                onChange={(change) => setDepartment(change.target.value)}
                aria-label="Department"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="School">
              <input
                type="text"
                value={school}
                onChange={(change) => setSchool(change.target.value)}
                aria-label="School"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Priority">
              <select
                value={priority}
                onChange={(change) => setPriority(change.target.value)}
                aria-label="Priority"
                className={FIELD_CLASS}
              >
                <option value="">— None —</option>
                {EVENT_PRIORITIES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Tags" hint="Comma-separated.">
              <input
                type="text"
                value={tags}
                onChange={(change) => setTags(change.target.value)}
                aria-label="Tags"
                className={FIELD_CLASS}
                placeholder="e.g. annual, outreach"
              />
            </Field>
          </div>

          <Field label="Description">
            <textarea
              value={description}
              onChange={(change) => setDescription(change.target.value)}
              aria-label="Description"
              rows={2}
              className={FIELD_CLASS}
            />
          </Field>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Objectives">
              <textarea
                value={objectives}
                onChange={(change) => setObjectives(change.target.value)}
                aria-label="Objectives"
                rows={2}
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Outcome">
              <textarea
                value={outcome}
                onChange={(change) => setOutcome(change.target.value)}
                aria-label="Outcome"
                rows={2}
                className={FIELD_CLASS}
              />
            </Field>
          </div>
          <Field label="Notes">
            <textarea
              value={notes}
              onChange={(change) => setNotes(change.target.value)}
              aria-label="Notes"
              rows={2}
              className={FIELD_CLASS}
            />
          </Field>

          <fieldset className="rounded-lg border border-[var(--border-subtle)] p-3">
            <legend className="px-1 text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
              Registration (PART 5)
            </legend>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Field label="Expected">
                <input
                  type="number"
                  min={0}
                  value={expected}
                  onChange={(change) => setExpected(change.target.value)}
                  aria-label="Expected participants"
                  className={FIELD_CLASS}
                />
              </Field>
              <Field label="Registered">
                <input
                  type="number"
                  min={0}
                  value={registered}
                  onChange={(change) => setRegistered(change.target.value)}
                  aria-label="Registered participants"
                  className={FIELD_CLASS}
                />
              </Field>
              <Field label="Present">
                <input
                  type="number"
                  min={0}
                  value={present}
                  onChange={(change) => setPresent(change.target.value)}
                  aria-label="Present participants"
                  className={FIELD_CLASS}
                />
              </Field>
              <Field label="Certificates issued">
                <input
                  type="number"
                  min={0}
                  value={certificatesIssued}
                  onChange={(change) => setCertificatesIssued(change.target.value)}
                  aria-label="Certificates issued"
                  className={FIELD_CLASS}
                />
              </Field>
            </div>
          </fieldset>

          <fieldset className="rounded-lg border border-[var(--border-subtle)] p-3">
            <legend className="px-1 text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
              Linked people &amp; research (PART 7)
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Faculty">
                <MultiSelect
                  label="Linked faculty"
                  options={facultyOptions}
                  selected={facultyIds}
                  onChange={setFacultyIds}
                />
              </Field>
              <Field label="Students">
                <MultiSelect
                  label="Linked students"
                  options={studentOptions}
                  selected={studentIds}
                  onChange={setStudentIds}
                />
              </Field>
              <Field label="Research projects">
                <MultiSelect
                  label="Linked projects"
                  options={projectOptions}
                  selected={projectIds}
                  onChange={setProjectIds}
                />
              </Field>
              <Field label="Grants">
                <MultiSelect
                  label="Linked grants"
                  options={grantOptions}
                  selected={grantIds}
                  onChange={setGrantIds}
                />
              </Field>
              <Field label="Committees">
                <MultiSelect
                  label="Linked committees"
                  options={committeeOptions}
                  selected={committeeIds}
                  onChange={setCommitteeIds}
                />
              </Field>
            </div>
          </fieldset>

          <Field label="Added by" hint="Audit-trail actor recorded on every save.">
            <input
              type="text"
              value={uploadedBy}
              onChange={(change) => setUploadedBy(change.target.value)}
              aria-label="Added by"
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
            {submitting ? "Saving…" : mode === "edit" ? "Save changes" : "Create event"}
          </button>
        </div>
      </form>
    </div>
  );
}

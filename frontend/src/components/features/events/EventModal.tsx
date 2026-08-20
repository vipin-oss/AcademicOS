"use client";

/**
 * EventModal — create / edit an Event with progressive disclosure.
 *
 * Essential fields (always visible): Title, Type, Dates, Venue, Mode
 * Advanced fields (expandable): Status, Organizer, Department, Code, Priority,
 *   Description, Objectives, Outcome, Notes, Tags, Registration, Links
 */

import { useEffect, useRef, useState } from "react";
import { X, ChevronDown, ChevronRight } from "lucide-react";
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

function Field({ label, error, hint, children }: {
  label: string; error?: string | null; hint?: string; children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      {children}
      {error ? <p role="alert" className="mt-1 text-xs text-[var(--danger)]">{error}</p> :
        hint ? <p className="mt-1 text-xs text-[var(--text-tertiary)]">{hint}</p> : null}
    </label>
  );
}

interface PickerOption { id: string; label: string; }

function MultiSelect({ label, options, selected, onChange }: {
  label: string; options: PickerOption[]; selected: string[]; onChange: (ids: string[]) => void;
}) {
  return (
    <select multiple value={selected}
      onChange={(e) => onChange(Array.from(e.target.selectedOptions).map((o) => o.value))}
      className={MULTI_SELECT_CLASS} aria-label={label}>
      {options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
    </select>
  );
}

export interface EventSaveResult { event: EventResponse; mode: "create" | "edit"; }

export function EventModal({ open, onClose, onSaved, event }: {
  open: boolean; onClose: () => void; onSaved: (result: EventSaveResult) => void;
  event?: EventResponse | null;
}) {
  const mode = event ? "edit" : "create";
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Essential fields
  const [title, setTitle] = useState("");
  const [eventType, setEventType] = useState<EventType>("custom");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [venue, setVenue] = useState("");
  const [eventMode, setEventMode] = useState("");

  // Advanced fields
  const [eventCode, setEventCode] = useState("");
  const [organizer, setOrganizer] = useState("");
  const [coOrganizer, setCoOrganizer] = useState("");
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
    setFacultyIds((event?.links?.faculty ?? []).map((l) => l.id));
    setStudentIds((event?.links?.students ?? []).map((l) => l.id));
    setProjectIds((event?.links?.projects ?? []).map((l) => l.id));
    setGrantIds((event?.links?.grants ?? []).map((l) => l.id));
    setCommitteeIds((event?.links?.committees ?? []).map((l) => l.id));
    setUploadedBy(event?.uploaded_by ?? "faculty:ui");
    setStatus(event?.status ?? "active");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
    setShowAdvanced(!!event); // Show advanced when editing
  }, [open, event]);

  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    listFaculty({ pageSize: 100 }, { signal: ctrl.signal })
      .then((r) => setFacultyOptions(r.items.map((p) => ({ id: p.id, label: p.name }))))
      .catch(() => setFacultyOptions([]));
    listStudents({ pageSize: 100 }, { signal: ctrl.signal })
      .then((r) => setStudentOptions(r.items.map((s) => ({ id: s.id, label: s.name }))))
      .catch(() => setStudentOptions([]));
    listProjects({ pageSize: 100 }, { signal: ctrl.signal })
      .then((r) => setProjectOptions(r.items.map((p) => ({ id: p.id, label: p.title }))))
      .catch(() => setProjectOptions([]));
    listGrants({ pageSize: 100 }, { signal: ctrl.signal })
      .then((r) => setGrantOptions(r.items.map((g) => ({ id: g.id, label: g.title }))))
      .catch(() => setGrantOptions([]));
    listCommittees({ pageSize: 100 }, { signal: ctrl.signal })
      .then((r) => setCommitteeOptions(r.items.map((c) => ({ id: c.id, label: c.name }))))
      .catch(() => setCommitteeOptions([]));
    return () => ctrl.abort();
  }, [open]);

  useEffect(() => { if (open) firstFieldRef.current?.focus(); }, [open]);

  if (!open) return null;

  const handleClose = () => { if (!submittingRef.current) onClose(); };

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);
    if (!title.trim()) { setFormError("Event title is required."); return; }
    if (startDate && endDate && endDate < startDate) { setFormError("End date cannot be before start date."); return; }
    const counters = {
      expected_participants: counterValue(expected, "Expected"),
      registered: counterValue(registered, "Registered"),
      present: counterValue(present, "Present"),
      certificates_issued: counterValue(certificatesIssued, "Certificates"),
    };
    if (Object.values(counters).some((v) => Number.isNaN(v))) return;

    submittingRef.current = true;
    setSubmitting(true);
    const split = (raw: string) => raw.split(",").map((p) => p.trim()).filter(Boolean);

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
      tags: split(tags),
      registration: counters,
      links: { faculty: facultyIds, students: studentIds, projects: projectIds, grants: grantIds, committees: committeeIds } as Partial<Record<EventInputLinkGroup, string[]>>,
    };

    try {
      const saved = event ? await updateEvent(event.id, payload) : await createEvent(payload);
      onSaved({ event: saved, mode });
    } catch (err) { setFormError(toErrorMessage(err)); }
    finally { submittingRef.current = false; setSubmitting(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      onMouseDown={(e) => { if (e.target === e.currentTarget) handleClose(); }}>
      <form role="dialog" aria-modal="true" aria-labelledby="event-modal-title" onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl">

        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 id="event-modal-title" className="text-base font-semibold text-[var(--text-primary)]">
            {mode === "edit" ? "Edit Event" : "New Event"}
          </h2>
          <button type="button" onClick={handleClose} aria-label="Close"
            className="rounded-lg p-1.5 text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)]">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {/* Essential fields — always visible */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field label="Event title *">
                <input ref={firstFieldRef} type="text" value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className={FIELD_CLASS} placeholder="e.g. International Conference on AI 2026" />
              </Field>
            </div>
            <Field label="Type">
              <select value={eventType} onChange={(e) => setEventType(e.target.value as EventType)} className={FIELD_CLASS}>
                {EVENT_TYPES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
            <Field label="Mode">
              <select value={eventMode} onChange={(e) => setEventMode(e.target.value)} className={FIELD_CLASS}>
                <option value="">-- Select --</option>
                {EVENT_MODES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
            <Field label="Start date">
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className={FIELD_CLASS} />
            </Field>
            <Field label="End date">
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className={FIELD_CLASS} />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Venue">
                <input type="text" value={venue} onChange={(e) => setVenue(e.target.value)}
                  className={FIELD_CLASS} placeholder="e.g. Vigyan Bhawan, New Delhi" />
              </Field>
            </div>
          </div>

          {/* Advanced fields — collapsible */}
          <button type="button" onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-1.5 text-sm font-medium text-[var(--accent)] hover:underline">
            {showAdvanced ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            {showAdvanced ? "Hide additional details" : "More details (optional)"}
          </button>

          {showAdvanced && (
            <div className="space-y-4 border-t border-[var(--border-subtle)] pt-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Status">
                  <select value={eventStatus} onChange={(e) => setEventStatus(e.target.value as EventStatus)} className={FIELD_CLASS}>
                    {EVENT_STATUSES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </Field>
                <Field label="Event code" hint="Unique when provided (e.g. EVT-2026-001)">
                  <input type="text" value={eventCode} onChange={(e) => setEventCode(e.target.value)} className={FIELD_CLASS} />
                </Field>
                <Field label="Organizer">
                  <input type="text" value={organizer} onChange={(e) => setOrganizer(e.target.value)} className={FIELD_CLASS} placeholder="e.g. Dept. of Mathematics" />
                </Field>
                <Field label="Co-organizer">
                  <input type="text" value={coOrganizer} onChange={(e) => setCoOrganizer(e.target.value)} className={FIELD_CLASS} />
                </Field>
                <Field label="Department">
                  <input type="text" value={department} onChange={(e) => setDepartment(e.target.value)} className={FIELD_CLASS} />
                </Field>
                <Field label="School">
                  <input type="text" value={school} onChange={(e) => setSchool(e.target.value)} className={FIELD_CLASS} />
                </Field>
                <Field label="Priority">
                  <select value={priority} onChange={(e) => setPriority(e.target.value)} className={FIELD_CLASS}>
                    <option value="">-- None --</option>
                    {EVENT_PRIORITIES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </Field>
                <Field label="Tags" hint="Comma-separated">
                  <input type="text" value={tags} onChange={(e) => setTags(e.target.value)} className={FIELD_CLASS} placeholder="e.g. annual, outreach" />
                </Field>
              </div>

              <Field label="Description">
                <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className={FIELD_CLASS} />
              </Field>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Objectives"><textarea value={objectives} onChange={(e) => setObjectives(e.target.value)} rows={2} className={FIELD_CLASS} /></Field>
                <Field label="Outcome"><textarea value={outcome} onChange={(e) => setOutcome(e.target.value)} rows={2} className={FIELD_CLASS} /></Field>
              </div>
              <Field label="Notes"><textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className={FIELD_CLASS} /></Field>

              <fieldset className="rounded-lg border border-[var(--border-subtle)] p-3">
                <legend className="px-1 text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">Registration</legend>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Field label="Expected"><input type="number" min={0} value={expected} onChange={(e) => setExpected(e.target.value)} className={FIELD_CLASS} /></Field>
                  <Field label="Registered"><input type="number" min={0} value={registered} onChange={(e) => setRegistered(e.target.value)} className={FIELD_CLASS} /></Field>
                  <Field label="Present"><input type="number" min={0} value={present} onChange={(e) => setPresent(e.target.value)} className={FIELD_CLASS} /></Field>
                  <Field label="Certificates"><input type="number" min={0} value={certificatesIssued} onChange={(e) => setCertificatesIssued(e.target.value)} className={FIELD_CLASS} /></Field>
                </div>
              </fieldset>

              <fieldset className="rounded-lg border border-[var(--border-subtle)] p-3">
                <legend className="px-1 text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">Linked records</legend>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Field label="Faculty"><MultiSelect label="Faculty" options={facultyOptions} selected={facultyIds} onChange={setFacultyIds} /></Field>
                  <Field label="Students"><MultiSelect label="Students" options={studentOptions} selected={studentIds} onChange={setStudentIds} /></Field>
                  <Field label="Projects"><MultiSelect label="Projects" options={projectOptions} selected={projectIds} onChange={setProjectIds} /></Field>
                  <Field label="Grants"><MultiSelect label="Grants" options={grantOptions} selected={grantIds} onChange={setGrantIds} /></Field>
                  <Field label="Committees"><MultiSelect label="Committees" options={committeeOptions} selected={committeeIds} onChange={setCommitteeIds} /></Field>
                </div>
              </fieldset>
            </div>
          )}

          {formError && (
            <p role="alert" className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
              {formError}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 border-t border-[var(--border-subtle)] px-5 py-4">
          <button type="button" onClick={handleClose} disabled={submitting}
            className="rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-50">
            Cancel
          </button>
          <button type="submit" disabled={submitting}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:opacity-60">
            {submitting ? <Spinner /> : null}
            {submitting ? "Saving..." : mode === "edit" ? "Save changes" : "Create event"}
          </button>
        </div>
      </form>
    </div>
  );
}

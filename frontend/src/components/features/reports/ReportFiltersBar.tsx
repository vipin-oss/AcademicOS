"use client";

import { useEffect, useState } from "react";
import { listFaculty } from "@/lib/api/faculty";
import { listStudents } from "@/lib/api/students";
import { listGrants, listProjects } from "@/lib/api/research";
import { listEvents } from "@/lib/api/events";
import { listCommittees } from "@/lib/api/committees";
import { YEAR_OPTIONS, reportKind } from "@/lib/reports/constants";
import type { ReportFilters } from "@/types";

interface PickerOption {
  id: string;
  label: string;
}

const SELECT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-2 py-1.5 text-sm text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none";
const INPUT_CLASS = SELECT_CLASS;

function Picker({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: PickerOption[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={SELECT_CLASS}
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

/**
 * PART 12 filter bar — renders exactly the pickers the active report kind
 * honours (the backend's FILTER_KEYS_BY_KIND contract, mirrored in
 * `lib/reports/constants`). Everything else hides so a filter can never
 * silently not-apply.
 */
export function ReportFiltersBar({
  kind,
  filters,
  onChange,
}: {
  kind: string;
  filters: ReportFilters;
  onChange: (filters: ReportFilters) => void;
}) {
  const honoured = new Set<string>(reportKind(kind)?.filters ?? []);
  const [options, setOptions] = useState<Record<string, PickerOption[]>>({});

  useEffect(() => {
    const controller = new AbortController();
    const opts = { signal: controller.signal };
    listFaculty({ pageSize: 100 }, opts)
      .then((r) =>
        setOptions((prev) => ({
          ...prev,
          faculty_id: r.items.map((p) => ({ id: p.id, label: p.name })),
        })),
      )
      .catch(() => undefined);
    listStudents({ pageSize: 100 }, opts)
      .then((r) =>
        setOptions((prev) => ({
          ...prev,
          student_id: r.items.map((s) => ({ id: s.id, label: s.name })),
        })),
      )
      .catch(() => undefined);
    listProjects({ pageSize: 100 }, opts)
      .then((r) =>
        setOptions((prev) => ({
          ...prev,
          project_id: r.items.map((p) => ({ id: p.id, label: p.title })),
        })),
      )
      .catch(() => undefined);
    listGrants({ pageSize: 100 }, opts)
      .then((r) =>
        setOptions((prev) => ({
          ...prev,
          grant_id: r.items.map((g) => ({ id: g.id, label: g.title })),
        })),
      )
      .catch(() => undefined);
    listEvents({ pageSize: 100 }, opts)
      .then((r) =>
        setOptions((prev) => ({
          ...prev,
          event_id: r.items.map((e) => ({ id: e.id, label: e.title })),
        })),
      )
      .catch(() => undefined);
    listCommittees({ pageSize: 100 }, opts)
      .then((r) =>
        setOptions((prev) => ({
          ...prev,
          committee_id: r.items.map((c) => ({ id: c.id, label: c.name })),
        })),
      )
      .catch(() => undefined);
    return () => controller.abort();
  }, [kind]);

  const set = (key: keyof ReportFilters) => (value: string) =>
    onChange({ ...filters, [key]: value || undefined });

  const anyActive = Object.values(filters).some((v) => v);

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5 shadow-sm">
      <div className="flex flex-wrap items-end gap-3">
        {honoured.has("year") ? (
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">Year</span>
            <select
              aria-label="Year"
              value={filters.year ?? ""}
              onChange={(event) => set("year")(event.target.value)}
              className={SELECT_CLASS}
            >
              <option value="">All</option>
              {YEAR_OPTIONS.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {honoured.has("date_from") ? (
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">From</span>
            <input
              type="date"
              aria-label="From date"
              value={filters.date_from ?? ""}
              onChange={(event) => set("date_from")(event.target.value)}
              className={INPUT_CLASS}
            />
          </label>
        ) : null}
        {honoured.has("date_to") ? (
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">To</span>
            <input
              type="date"
              aria-label="To date"
              value={filters.date_to ?? ""}
              onChange={(event) => set("date_to")(event.target.value)}
              className={INPUT_CLASS}
            />
          </label>
        ) : null}
        {honoured.has("department") ? (
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">Department</span>
            <input
              type="text"
              aria-label="Department"
              placeholder="e.g. Mathematics"
              value={filters.department ?? ""}
              onChange={(event) => set("department")(event.target.value)}
              className={INPUT_CLASS}
            />
          </label>
        ) : null}
        {(["faculty_id", "student_id", "project_id", "grant_id", "event_id", "committee_id"] as const)
          .filter((key) => honoured.has(key))
          .map((key) => (
            <Picker
              key={key}
              label={{
                faculty_id: "Faculty",
                student_id: "Student",
                project_id: "Project",
                grant_id: "Grant",
                event_id: "Event",
                committee_id: "Committee",
              }[key]}
              value={filters[key] ?? ""}
              options={options[key] ?? []}
              onChange={set(key)}
            />
          ))}
        {anyActive ? (
          <button
            type="button"
            onClick={() => onChange({})}
            className="rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            Clear filters
          </button>
        ) : null}
      </div>
    </div>
  );
}

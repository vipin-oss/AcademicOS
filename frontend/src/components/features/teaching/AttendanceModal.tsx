"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCheck, X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { importAttendanceCsv, recordAttendance } from "@/lib/api/teaching";
import { ATTENDANCE_CSV_SAMPLE, ATTENDANCE_STATES } from "@/lib/teaching/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type {
  AttendanceImportResult,
  AttendanceSessionResponse,
  AttendanceState,
  RosterEntry,
} from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

/** Today's date, register style (YYYY-MM-DD). */
function todayIso(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/**
 * Record one day of attendance (PART I): Manual — a select per roster
 * student with an "All present" register shortcut — or CSV Import (Roll No,
 * Status: P/A/L/ML). One session per (class, date): re-recording the same
 * date UPDATES it (the backend upserts), so passing `session` re-opens that
 * day for correction.
 */
export function AttendanceModal({
  open,
  classId,
  roster,
  session = null,
  onClose,
  onRecorded,
  onImported,
}: {
  open: boolean;
  classId: string;
  roster: RosterEntry[];
  /** Existing session to correct (its date + states prefill the form). */
  session?: AttendanceSessionResponse | null;
  onClose: () => void;
  onRecorded: (recorded: AttendanceSessionResponse) => void;
  onImported: (result: AttendanceImportResult) => void;
}) {
  const [tab, setTab] = useState<"manual" | "csv">("manual");
  const [date, setDate] = useState(todayIso());
  const [states, setStates] = useState<Record<string, AttendanceState>>({});
  const [csvText, setCsvText] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setTab("manual");
    setDate(session?.session_date ?? todayIso());
    setStates(() => {
      // Prefill from the session being corrected; everyone else = present
      // (the register default) so a quick day is two clicks.
      const initial: Record<string, AttendanceState> = {};
      for (const entry of roster) {
        initial[entry.student_id] = session?.records?.[entry.student_id] ?? "present";
      }
      return initial;
    });
    setCsvText("");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
    setTimeout(() => firstFieldRef.current?.focus(), 50);
  }, [open, session, roster]);

  if (!open) return null;

  const markAll = (state: AttendanceState) => {
    setStates(() => {
      const next: Record<string, AttendanceState> = {};
      for (const entry of roster) next[entry.student_id] = state;
      return next;
    });
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);
    if (!date.trim()) {
      setFormError("Pick the session date first.");
      return;
    }
    if (tab === "csv" && !csvText.trim()) {
      setFormError("Paste an attendance CSV first (header row required).");
      return;
    }
    submittingRef.current = true;
    setSubmitting(true);
    try {
      if (tab === "manual") {
        const recorded = await recordAttendance(classId, {
          session_date: date.trim(),
          records: states,
          actor: "faculty:ui",
        });
        onRecorded(recorded);
      } else {
        const outcome = await importAttendanceCsv(classId, {
          session_date: date.trim(),
          text: csvText,
          actor: "faculty:ui",
        });
        onImported(outcome);
      }
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
        aria-labelledby="attendance-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="attendance-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            {session ? `Correct Attendance · ${session.session_date}` : "Record Attendance"}
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
            <p
              role="alert"
              className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
            >
              {formError}
            </p>
          ) : null}

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
              Session date
            </span>
            <input
              ref={firstFieldRef}
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
              className={FIELD_CLASS}
              aria-label="Session date"
            />
          </label>

          <div role="tablist" aria-label="Attendance mode" className="flex gap-2">
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
                {value === "manual" ? "Mark register" : "CSV import"}
              </button>
            ))}
          </div>

          {tab === "manual" ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-[var(--text-tertiary)]">
                  One state per student — students left out of a day count as absent in
                  the summary.
                </p>
                <button
                  type="button"
                  onClick={() => markAll("present")}
                  className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                >
                  <CheckCheck className="h-3.5 w-3.5" aria-hidden="true" /> All present
                </button>
              </div>
              <div className="max-h-72 overflow-y-auto rounded-lg border border-[var(--border-subtle)]">
                {roster.length === 0 ? (
                  <p className="px-3 py-3 text-sm text-[var(--text-tertiary)]">
                    The roster is empty — enroll students first.
                  </p>
                ) : (
                  <ul className="divide-y divide-[var(--border-subtle)]">
                    {roster.map((entry) => (
                      <li key={entry.student_id} className="flex items-center gap-2.5 px-3 py-2">
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm text-[var(--text-primary)]">
                            {entry.name}
                          </span>
                          <span className="text-xs text-[var(--text-tertiary)]">
                            {entry.roll_number ?? "—"}
                          </span>
                        </span>
                        <select
                          value={states[entry.student_id] ?? "present"}
                          onChange={(event) =>
                            setStates((current) => ({
                              ...current,
                              [entry.student_id]: event.target.value as AttendanceState,
                            }))
                          }
                          aria-label={`Attendance for ${entry.name}`}
                          className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
                        >
                          {ATTENDANCE_STATES.map(({ value, label }) => (
                            <option key={value} value={value}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-[var(--text-secondary)]">
                One row per student — roll number + status (
                <span className="text-[var(--text-tertiary)]">
                  P / A / L / ML, full words also work
                </span>
                ). The header row is required.
              </p>
              <textarea
                value={csvText}
                onChange={(event) => setCsvText(event.target.value)}
                rows={6}
                className={`${FIELD_CLASS} font-mono text-xs`}
                placeholder={ATTENDANCE_CSV_SAMPLE}
                aria-label="Attendance CSV text"
              />
              <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]">
                …or choose a .csv file
                <input
                  type="file"
                  accept=".csv,text/csv,text/plain"
                  className="hidden"
                  aria-label="Choose a CSV file"
                  onChange={async (event) => {
                    const file = event.target.files?.[0];
                    if (file) setCsvText(await file.text());
                    event.target.value = "";
                  }}
                />
              </label>
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
            disabled={submitting || roster.length === 0}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
          >
            {submitting ? <Spinner className="h-4 w-4" /> : null}
            {tab === "manual" ? "Record" : "Import"}
          </button>
        </div>
      </form>
    </div>
  );
}

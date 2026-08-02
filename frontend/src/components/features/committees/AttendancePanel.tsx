"use client";

import { useEffect, useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { updateMeeting } from "@/lib/api/committees";
import { ATTENDANCE_STATUSES } from "@/lib/committees/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import { AttendanceStatusBadge } from "./CommitteeBadges";
import type {
  AttendanceEntry,
  AttendanceStatus,
  CommitteeMember,
  MeetingResponse,
} from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

interface AttendanceRow {
  /** Person id when the attendee is a committee member (else free-text name). */
  object_id: string;
  name: string;
  status: AttendanceStatus;
}

function toRows(entries: AttendanceEntry[]): AttendanceRow[] {
  return entries.map((entry) => ({
    object_id: entry.object_id ?? "",
    name: entry.name ?? "",
    status: entry.status ?? "present",
  }));
}

/**
 * Meeting attendance (PART 3). Rows either reference a committee member
 * (object_id) or record an external guest by name. Whole-list replace through
 * the meeting update contract.
 */
export function AttendancePanel({
  meeting,
  members,
  onSaved,
  onError,
}: {
  meeting: MeetingResponse;
  /** Committee members feed the attendee picker. */
  members: CommitteeMember[];
  onSaved: (meeting: MeetingResponse) => void;
  onError: (message: string) => void;
}) {
  const [rows, setRows] = useState<AttendanceRow[]>(() => toRows(meeting.attendance));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setRows(toRows(meeting.attendance));
  }, [meeting.attendance]);

  const addRow = () =>
    setRows((current) => [...current, { object_id: "", name: "", status: "present" }]);

  const removeRow = (index: number) =>
    setRows((current) => current.filter((_, rowIndex) => rowIndex !== index));

  const patchRow = (index: number, patch: Partial<AttendanceRow>) =>
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );

  const handleSave = async () => {
    if (saving) return;
    const incomplete = rows.find((row) => !row.object_id && !row.name.trim());
    if (incomplete) {
      onError("Every attendance row needs a member selected or a guest name (or remove it).");
      return;
    }
    setSaving(true);
    try {
      const payload: AttendanceEntry[] = rows.map((row) => {
        const member = members.find((candidate) => candidate.id === row.object_id);
        if (member) {
          return { object_id: member.id, name: member.name, status: row.status };
        }
        return { name: row.name.trim(), status: row.status };
      });
      const updated = await updateMeeting(meeting.id, {
        attendance: payload,
        uploaded_by: meeting.uploaded_by || "faculty:ui",
      });
      onSaved(updated);
    } catch (err) {
      onError(toErrorMessage(err, "Could not save the attendance."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section
      aria-label="Attendance"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Attendance ({rows.length})
        </h2>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={addRow}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add attendee
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-60"
          >
            {saving ? <Spinner className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" aria-hidden="true" />}
            {saving ? "Saving…" : "Save attendance"}
          </button>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No attendance recorded — add committee members and any external guests.
        </p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row, index) => (
            <li
              key={index}
              className="grid grid-cols-1 items-end gap-2 sm:grid-cols-[1fr_1fr_130px_auto]"
            >
              <label className="block">
                <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                  Committee member
                </span>
                <select
                  value={row.object_id}
                  onChange={(event) =>
                    patchRow(index, { object_id: event.target.value, name: "" })
                  }
                  aria-label={`Attendee ${index + 1} member`}
                  className={FIELD_CLASS}
                >
                  <option value="">— external guest —</option>
                  {members.map((member) => (
                    <option key={member.id} value={member.id}>
                      {member.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                  Guest name
                </span>
                <input
                  type="text"
                  value={row.object_id ? "" : row.name}
                  disabled={Boolean(row.object_id)}
                  onChange={(event) => patchRow(index, { name: event.target.value })}
                  aria-label={`Attendee ${index + 1} guest name`}
                  placeholder="External expert / invitee"
                  className={FIELD_CLASS}
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                  Status
                </span>
                <select
                  value={row.status}
                  onChange={(event) =>
                    patchRow(index, { status: event.target.value as AttendanceStatus })
                  }
                  aria-label={`Attendee ${index + 1} status`}
                  className={FIELD_CLASS}
                >
                  {ATTENDANCE_STATUSES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={() => removeRow(index)}
                aria-label={`Remove attendee ${index + 1}`}
                className="rounded-lg p-2 text-[var(--danger)] transition-colors hover:bg-[var(--danger-subtle)]"
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </button>
              <div className="sm:col-span-4">
                <AttendanceStatusBadge status={row.status} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

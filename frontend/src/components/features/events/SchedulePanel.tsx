"use client";

import { useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { updateEvent } from "@/lib/api/events";
import {
  SectionPanel,
  RowField,
  RowGrid,
  RowSelect,
  RowTextInput,
  RemoveRowButton,
  clean,
} from "@/components/features/finance/SectionPanel";
import { formatDate } from "@/lib/utils";
import type { EventResponse, ScheduleRow } from "@/types";

const ROW_FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

/** Native 24-hour time input (finance's RowTextInput covers text/date/number). */
function RowTimeInput({
  value,
  onChange,
  ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  ariaLabel: string;
}) {
  return (
    <input
      type="time"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      aria-label={ariaLabel}
      className={ROW_FIELD_CLASS}
    />
  );
}

export interface ScheduleEditRow {
  title: string;
  session_date: string;
  start_time: string;
  end_time: string;
  speaker_id: string;
  venue: string;
  chairperson: string;
  remarks: string;
}

function toEditRow(row: ScheduleRow): ScheduleEditRow {
  return {
    title: row.title ?? "",
    session_date: row.session_date ?? "",
    start_time: row.start_time ?? "",
    end_time: row.end_time ?? "",
    speaker_id: row.speaker_id ?? "",
    venue: row.venue ?? "",
    chairperson: row.chairperson ?? "",
    remarks: row.remarks ?? "",
  };
}

function blankRow(): ScheduleEditRow {
  return {
    title: "",
    session_date: "",
    start_time: "",
    end_time: "",
    speaker_id: "",
    venue: "",
    chairperson: "",
    remarks: "",
  };
}

function isFilled(row: ScheduleEditRow): boolean {
  return Boolean(
    clean(row.title) ||
      clean(row.session_date) ||
      clean(row.start_time) ||
      clean(row.end_time) ||
      row.speaker_id ||
      clean(row.venue) ||
      clean(row.chairperson) ||
      clean(row.remarks),
  );
}

/**
 * PART 4 schedule sessions. The speaker select offers this event's speakers
 * (stored as a stable speaker row_id; the name resolves server-side).
 */
export function SchedulePanel({
  event,
  onUpdated,
}: {
  event: EventResponse;
  onUpdated: (event: EventResponse) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<ScheduleEditRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setRows(event.schedule.map(toEditRow));
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setError(null);
  };

  const patchRow = (index: number, patch: Partial<ScheduleEditRow>) =>
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );

  const save = async () => {
    if (saving) return;
    setError(null);
    const filled = rows.filter(isFilled);
    if (filled.some((row) => !clean(row.title))) {
      setError("Every session needs a title (or remove the row).");
      return;
    }
    if (
      filled.some(
        (row) => clean(row.start_time) && clean(row.end_time) && row.end_time < row.start_time,
      )
    ) {
      setError("A session's end time must not be before its start time.");
      return;
    }

    setSaving(true);
    const payload = filled.map((row) => ({
      title: clean(row.title),
      session_date: clean(row.session_date),
      start_time: clean(row.start_time),
      end_time: clean(row.end_time),
      speaker_id: row.speaker_id || undefined,
      venue: clean(row.venue),
      chairperson: clean(row.chairperson),
      remarks: clean(row.remarks),
    }));
    try {
      const updated = await updateEvent(event.id, { schedule: payload });
      onUpdated(updated);
      setSaving(false);
      setEditing(false);
    } catch (err) {
      setSaving(false);
      setError(toErrorMessage(err));
    }
  };

  const speakerOptions = event.speakers
    .filter((speaker) => speaker.row_id && speaker.name)
    .map((speaker) => ({ value: speaker.row_id as string, label: speaker.name as string }));

  const view = (
    <>
      {event.schedule.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No sessions scheduled yet — edit to build the programme.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                <th className="py-2 pr-3 font-medium">Session</th>
                <th className="py-2 pr-3 font-medium">Date</th>
                <th className="py-2 pr-3 font-medium">Time</th>
                <th className="py-2 pr-3 font-medium">Speaker</th>
                <th className="py-2 pr-3 font-medium">Venue</th>
                <th className="py-2 pr-3 font-medium">Chairperson</th>
                <th className="py-2 font-medium">Remarks</th>
              </tr>
            </thead>
            <tbody>
              {event.schedule.map((row, index) => (
                <tr
                  key={index}
                  className="border-b border-[var(--border-subtle)] last:border-0"
                >
                  <td className="py-2 pr-3 font-medium text-[var(--text-primary)]">
                    {row.title || "—"}
                  </td>
                  <td className="py-2 pr-3">
                    {row.session_date ? formatDate(row.session_date) : "—"}
                  </td>
                  <td className="py-2 pr-3">
                    {row.start_time
                      ? row.end_time
                        ? `${row.start_time} – ${row.end_time}`
                        : row.start_time
                      : "—"}
                  </td>
                  <td className="py-2 pr-3">{row.speaker_name || "—"}</td>
                  <td className="py-2 pr-3">{row.venue || "—"}</td>
                  <td className="py-2 pr-3">{row.chairperson || "—"}</td>
                  <td className="py-2">{row.remarks || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );

  const editor = (
    <ul className="space-y-2">
      {rows.map((row, index) => (
        <RowGrid key={index}>
          <RowField label="Session title *">
            <RowTextInput
              value={row.title}
              onChange={(value) => patchRow(index, { title: value })}
              ariaLabel={`Session ${index + 1} title`}
              placeholder="e.g. Keynote"
            />
          </RowField>
          <RowField label="Date">
            <RowTextInput
              type="date"
              value={row.session_date}
              onChange={(value) => patchRow(index, { session_date: value })}
              ariaLabel={`Session ${index + 1} date`}
            />
          </RowField>
          <RowField label="Start time">
            <RowTimeInput
              value={row.start_time}
              onChange={(value) => patchRow(index, { start_time: value })}
              ariaLabel={`Session ${index + 1} start time`}
            />
          </RowField>
          <RowField label="End time">
            <RowTimeInput
              value={row.end_time}
              onChange={(value) => patchRow(index, { end_time: value })}
              ariaLabel={`Session ${index + 1} end time`}
            />
          </RowField>
          <RowField label="Speaker">
            <RowSelect
              value={row.speaker_id}
              onChange={(value) => patchRow(index, { speaker_id: value })}
              ariaLabel={`Session ${index + 1} speaker`}
              options={speakerOptions}
              emptyLabel="— No speaker —"
            />
          </RowField>
          <RowField label="Venue">
            <RowTextInput
              value={row.venue}
              onChange={(value) => patchRow(index, { venue: value })}
              ariaLabel={`Session ${index + 1} venue`}
              placeholder="Optional"
            />
          </RowField>
          <RowField label="Chairperson">
            <RowTextInput
              value={row.chairperson}
              onChange={(value) => patchRow(index, { chairperson: value })}
              ariaLabel={`Session ${index + 1} chairperson`}
              placeholder="Optional"
            />
          </RowField>
          <RowField label="Remarks">
            <RowTextInput
              value={row.remarks}
              onChange={(value) => patchRow(index, { remarks: value })}
              ariaLabel={`Session ${index + 1} remarks`}
              placeholder="Optional"
            />
          </RowField>
          <RemoveRowButton
            onClick={() =>
              setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))
            }
            ariaLabel={`Remove session ${index + 1}`}
          />
        </RowGrid>
      ))}
    </ul>
  );

  return (
    <SectionPanel
      title="Schedule"
      count={event.schedule.length}
      ariaLabel="Schedule"
      editing={editing}
      saving={saving}
      error={error}
      onEdit={startEdit}
      onSave={save}
      onCancel={cancel}
      addLabel="Add session"
      onAdd={() => setRows((current) => [...current, blankRow()])}
      view={view}
      editor={editor}
    />
  );
}

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
  type PickerOption,
} from "@/components/features/finance/SectionPanel";
import { ParticipationRoleBadge } from "@/components/features/events/EventBadges";
import { PARTICIPATION_ROLES } from "@/lib/events/constants";
import type { EventResponse, ParticipationRow } from "@/types";

export interface ParticipationEditRow {
  role: string;
  contribution: string;
  certificate_document_id: string;
  remarks: string;
}

function toEditRow(row: ParticipationRow): ParticipationEditRow {
  return {
    role: row.role ?? "",
    contribution: row.contribution ?? "",
    certificate_document_id: row.certificate_document_id ?? "",
    remarks: row.remarks ?? "",
  };
}

function blankRow(): ParticipationEditRow {
  return { role: "", contribution: "", certificate_document_id: "", remarks: "" };
}

function isFilled(row: ParticipationEditRow): boolean {
  return Boolean(
    row.role || clean(row.contribution) || row.certificate_document_id || clean(row.remarks),
  );
}

/**
 * PART 2 "My Participation" — my roles in this event with certificates.
 * Rows are stored in event metadata; saving PUTs only the participation key.
 */
export function ParticipationPanel({
  event,
  documents,
  onUpdated,
}: {
  event: EventResponse;
  documents: PickerOption[];
  onUpdated: (event: EventResponse) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<ParticipationEditRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setRows(event.participation.map(toEditRow));
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setError(null);
  };

  const patchRow = (index: number, patch: Partial<ParticipationEditRow>) =>
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );

  const save = async () => {
    if (saving) return;
    setError(null);
    const filled = rows.filter(isFilled);
    if (filled.some((row) => !row.role)) {
      setError("Every participation row needs a role (or remove the row).");
      return;
    }

    setSaving(true);
    const payload: ParticipationRow[] = filled.map((row) => ({
      role: row.role as ParticipationRow["role"],
      contribution: clean(row.contribution),
      certificate_document_id: row.certificate_document_id || undefined,
      remarks: clean(row.remarks),
    }));
    try {
      const updated = await updateEvent(event.id, { participation: payload });
      onUpdated(updated);
      setSaving(false);
      setEditing(false);
    } catch (err) {
      setSaving(false);
      setError(toErrorMessage(err));
    }
  };

  const view = (
    <>
      {event.participation.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No participation recorded yet — edit to add your roles in this event.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                <th className="py-2 pr-3 font-medium">Role</th>
                <th className="py-2 pr-3 font-medium">Contribution</th>
                <th className="py-2 pr-3 font-medium">Certificate</th>
                <th className="py-2 font-medium">Remarks</th>
              </tr>
            </thead>
            <tbody>
              {event.participation.map((row, index) => (
                <tr
                  key={index}
                  className="border-b border-[var(--border-subtle)] last:border-0"
                >
                  <td className="py-2 pr-3">
                    {row.role ? <ParticipationRoleBadge role={row.role} /> : "—"}
                  </td>
                  <td className="py-2 pr-3">{row.contribution || "—"}</td>
                  <td className="py-2 pr-3">{row.certificate?.title || "—"}</td>
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
          <RowField label="Role *">
            <RowSelect
              value={row.role}
              onChange={(value) => patchRow(index, { role: value })}
              ariaLabel={`Participation ${index + 1} role`}
              options={PARTICIPATION_ROLES.map((role) => ({
                value: role.value,
                label: role.label,
              }))}
              emptyLabel="— Select role —"
            />
          </RowField>
          <RowField label="Contribution">
            <RowTextInput
              value={row.contribution}
              onChange={(value) => patchRow(index, { contribution: value })}
              ariaLabel={`Participation ${index + 1} contribution`}
              placeholder="What you did"
            />
          </RowField>
          <RowField label="Certificate">
            <RowSelect
              value={row.certificate_document_id}
              onChange={(value) => patchRow(index, { certificate_document_id: value })}
              ariaLabel={`Participation ${index + 1} certificate`}
              options={documents.map((document) => ({
                value: document.id,
                label: document.label,
              }))}
              emptyLabel="— No certificate —"
            />
          </RowField>
          <RowField label="Remarks">
            <RowTextInput
              value={row.remarks}
              onChange={(value) => patchRow(index, { remarks: value })}
              ariaLabel={`Participation ${index + 1} remarks`}
              placeholder="Optional"
            />
          </RowField>
          <RemoveRowButton
            onClick={() =>
              setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))
            }
            ariaLabel={`Remove participation ${index + 1}`}
          />
        </RowGrid>
      ))}
    </ul>
  );

  return (
    <SectionPanel
      title="My Participation"
      count={event.participation.length}
      ariaLabel="My Participation"
      editing={editing}
      saving={saving}
      error={error}
      onEdit={startEdit}
      onSave={save}
      onCancel={cancel}
      addLabel="Add participation"
      onAdd={() => setRows((current) => [...current, blankRow()])}
      view={view}
      editor={editor}
    />
  );
}

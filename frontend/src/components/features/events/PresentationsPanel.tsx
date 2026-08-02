"use client";

import { useState } from "react";
import Link from "next/link";
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
import { PresentationRelationBadge } from "@/components/features/events/EventBadges";
import { PRESENTATION_RELATIONS } from "@/lib/events/constants";
import type { EventResponse, PresentationRow } from "@/types";

export interface PresentationEditRow {
  publication_id: string;
  relation: string;
  remarks: string;
}

function toEditRow(row: PresentationRow): PresentationEditRow {
  return {
    publication_id: row.publication_id ?? "",
    relation: row.relation ?? "",
    remarks: row.remarks ?? "",
  };
}

function blankRow(): PresentationEditRow {
  return { publication_id: "", relation: "", remarks: "" };
}

function isFilled(row: PresentationEditRow): boolean {
  return Boolean(row.publication_id || row.relation || clean(row.remarks));
}

/**
 * PART 8 linked publications — every publication can be linked to the event
 * with a presentation relation (presented paper / proceedings / best paper /
 * poster). Saving PUTs only the presentations key; the publications edges
 * are derived server-side.
 */
export function PresentationsPanel({
  event,
  publications,
  onUpdated,
}: {
  event: EventResponse;
  publications: PickerOption[];
  onUpdated: (event: EventResponse) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<PresentationEditRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setRows(event.presentations.map(toEditRow));
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setError(null);
  };

  const patchRow = (index: number, patch: Partial<PresentationEditRow>) =>
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );

  const save = async () => {
    if (saving) return;
    setError(null);
    const filled = rows.filter(isFilled);
    if (filled.some((row) => !row.publication_id)) {
      setError("Every row needs a publication (or remove the row).");
      return;
    }
    const ids = filled.map((row) => row.publication_id);
    if (new Set(ids).size !== ids.length) {
      setError("Each publication may be linked only once per event.");
      return;
    }

    setSaving(true);
    const payload: PresentationRow[] = filled.map((row) => ({
      publication_id: row.publication_id,
      relation: (row.relation || undefined) as PresentationRow["relation"],
      remarks: clean(row.remarks),
    }));
    try {
      const updated = await updateEvent(event.id, { presentations: payload });
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
      {event.presentations.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No linked publications yet — edit to record presented papers,
          proceedings, awards and posters.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                <th className="py-2 pr-3 font-medium">Publication</th>
                <th className="py-2 pr-3 font-medium">Relation</th>
                <th className="py-2 font-medium">Remarks</th>
              </tr>
            </thead>
            <tbody>
              {event.presentations.map((row, index) => (
                <tr
                  key={index}
                  className="border-b border-[var(--border-subtle)] last:border-0"
                >
                  <td className="py-2 pr-3">
                    {row.publication_id ? (
                      <Link
                        href={`/publications/${encodeURIComponent(row.publication_id)}`}
                        className="text-[var(--accent)] hover:underline"
                      >
                        {row.publication_title || row.publication_id}
                      </Link>
                    ) : (
                      (row.publication_title ?? "—")
                    )}
                  </td>
                  <td className="py-2 pr-3">
                    {row.relation ? (
                      <PresentationRelationBadge relation={row.relation} />
                    ) : (
                      "—"
                    )}
                  </td>
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
          <RowField label="Publication *">
            <RowSelect
              value={row.publication_id}
              onChange={(value) => patchRow(index, { publication_id: value })}
              ariaLabel={`Presentation ${index + 1} publication`}
              options={publications.map((publication) => ({
                value: publication.id,
                label: publication.label,
              }))}
              emptyLabel="— Select publication —"
            />
          </RowField>
          <RowField label="Relation">
            <RowSelect
              value={row.relation}
              onChange={(value) => patchRow(index, { relation: value })}
              ariaLabel={`Presentation ${index + 1} relation`}
              options={PRESENTATION_RELATIONS.map((relation) => ({
                value: relation.value,
                label: relation.label,
              }))}
              emptyLabel="— Plain link —"
            />
          </RowField>
          <RowField label="Remarks">
            <RowTextInput
              value={row.remarks}
              onChange={(value) => patchRow(index, { remarks: value })}
              ariaLabel={`Presentation ${index + 1} remarks`}
              placeholder="Optional"
            />
          </RowField>
          <RemoveRowButton
            onClick={() =>
              setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))
            }
            ariaLabel={`Remove presentation ${index + 1}`}
          />
        </RowGrid>
      ))}
    </ul>
  );

  return (
    <SectionPanel
      title="Linked Publications"
      count={event.presentations.length}
      ariaLabel="Linked Publications"
      editing={editing}
      saving={saving}
      error={error}
      onEdit={startEdit}
      onSave={save}
      onCancel={cancel}
      addLabel="Add publication"
      onAdd={() => setRows((current) => [...current, blankRow()])}
      view={view}
      editor={editor}
    />
  );
}

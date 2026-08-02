"use client";

import { useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { updateEvent } from "@/lib/api/events";
import {
  SectionPanel,
  RowDocumentsSelect,
  RowField,
  RowGrid,
  RowSelect,
  RowTextInput,
  RemoveRowButton,
  clean,
  type PickerOption,
} from "@/components/features/finance/SectionPanel";
import type { EventResponse, SpeakerRow } from "@/types";

export interface SpeakerEditRow {
  row_id: string;
  name: string;
  affiliation: string;
  designation: string;
  email: string;
  phone: string;
  biography: string;
  photo_document_id: string;
  document_ids: string[];
}

function toEditRow(row: SpeakerRow): SpeakerEditRow {
  return {
    row_id: row.row_id ?? "",
    name: row.name ?? "",
    affiliation: row.affiliation ?? "",
    designation: row.designation ?? "",
    email: row.email ?? "",
    phone: row.phone ?? "",
    biography: row.biography ?? "",
    photo_document_id: row.photo_document_id ?? "",
    document_ids: row.document_ids ?? [],
  };
}

function blankRow(): SpeakerEditRow {
  return {
    row_id: "",
    name: "",
    affiliation: "",
    designation: "",
    email: "",
    phone: "",
    biography: "",
    photo_document_id: "",
    document_ids: [],
  };
}

function isFilled(row: SpeakerEditRow): boolean {
  return Boolean(
    clean(row.name) ||
      clean(row.affiliation) ||
      clean(row.designation) ||
      clean(row.email) ||
      clean(row.phone) ||
      clean(row.biography) ||
      row.photo_document_id ||
      row.document_ids.length > 0,
  );
}

/**
 * PART 3 speakers directory. `row_id` round-trips untouched (server-minted
 * when absent) so schedule sessions keep pointing at the right speaker.
 */
export function SpeakersPanel({
  event,
  documents,
  onUpdated,
}: {
  event: EventResponse;
  documents: PickerOption[];
  onUpdated: (event: EventResponse) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<SpeakerEditRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setRows(event.speakers.map(toEditRow));
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setError(null);
  };

  const patchRow = (index: number, patch: Partial<SpeakerEditRow>) =>
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );

  const save = async () => {
    if (saving) return;
    setError(null);
    const filled = rows.filter(isFilled);
    if (filled.some((row) => !clean(row.name))) {
      setError("Every speaker row needs a name (or remove the row).");
      return;
    }
    if (
      filled.some(
        (row) => clean(row.email) && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(row.email.trim()),
      )
    ) {
      setError("Speaker emails must be valid addresses.");
      return;
    }

    setSaving(true);
    const payload = filled.map((row) => ({
      row_id: row.row_id || undefined,
      name: clean(row.name),
      affiliation: clean(row.affiliation),
      designation: clean(row.designation),
      email: clean(row.email),
      phone: clean(row.phone),
      biography: clean(row.biography),
      photo_document_id: row.photo_document_id || undefined,
      document_ids: row.document_ids,
    }));
    try {
      const updated = await updateEvent(event.id, { speakers: payload });
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
      {event.speakers.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No speakers recorded yet — edit to add the resource persons.
        </p>
      ) : (
        <ul className="space-y-3">
          {event.speakers.map((speaker, index) => (
            <li
              key={speaker.row_id ?? index}
              className="rounded-lg border border-[var(--border-subtle)] p-3"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm font-medium text-[var(--text-primary)]">
                  {speaker.name}
                </p>
                {speaker.designation || speaker.affiliation ? (
                  <p className="text-xs text-[var(--text-tertiary)]">
                    {[speaker.designation, speaker.affiliation].filter(Boolean).join(" · ")}
                  </p>
                ) : null}
              </div>
              {speaker.biography ? (
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{speaker.biography}</p>
              ) : null}
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                {[speaker.email, speaker.phone].filter(Boolean).join(" · ") || "No contact details"}
              </p>
              {speaker.photo || (speaker.supporting_documents ?? []).length > 0 ? (
                <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                  {[speaker.photo?.title, ...(speaker.supporting_documents ?? []).map((d) => d.title)]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </>
  );

  const editor = (
    <ul className="space-y-2">
      {rows.map((row, index) => (
        <RowGrid key={index}>
          <RowField label="Name *">
            <RowTextInput
              value={row.name}
              onChange={(value) => patchRow(index, { name: value })}
              ariaLabel={`Speaker ${index + 1} name`}
              placeholder="e.g. Prof. S. Raman"
            />
          </RowField>
          <RowField label="Affiliation">
            <RowTextInput
              value={row.affiliation}
              onChange={(value) => patchRow(index, { affiliation: value })}
              ariaLabel={`Speaker ${index + 1} affiliation`}
              placeholder="e.g. IIT Delhi"
            />
          </RowField>
          <RowField label="Designation">
            <RowTextInput
              value={row.designation}
              onChange={(value) => patchRow(index, { designation: value })}
              ariaLabel={`Speaker ${index + 1} designation`}
              placeholder="e.g. Professor"
            />
          </RowField>
          <RowField label="Email">
            <RowTextInput
              value={row.email}
              onChange={(value) => patchRow(index, { email: value })}
              ariaLabel={`Speaker ${index + 1} email`}
              placeholder="name@institute.edu"
            />
          </RowField>
          <RowField label="Phone">
            <RowTextInput
              value={row.phone}
              onChange={(value) => patchRow(index, { phone: value })}
              ariaLabel={`Speaker ${index + 1} phone`}
            />
          </RowField>
          <RowField label="Biography">
            <RowTextInput
              value={row.biography}
              onChange={(value) => patchRow(index, { biography: value })}
              ariaLabel={`Speaker ${index + 1} biography`}
              placeholder="Optional"
            />
          </RowField>
          <RowField label="Photo">
            <RowSelect
              value={row.photo_document_id}
              onChange={(value) => patchRow(index, { photo_document_id: value })}
              ariaLabel={`Speaker ${index + 1} photo`}
              options={documents.map((document) => ({
                value: document.id,
                label: document.label,
              }))}
              emptyLabel="— No photo —"
            />
          </RowField>
          <RowField label="Documents">
            <RowDocumentsSelect
              value={row.document_ids}
              onChange={(ids) => patchRow(index, { document_ids: ids })}
              ariaLabel={`Speaker ${index + 1} documents`}
              options={documents}
            />
          </RowField>
          <RemoveRowButton
            onClick={() =>
              setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))
            }
            ariaLabel={`Remove speaker ${index + 1}`}
          />
        </RowGrid>
      ))}
    </ul>
  );

  return (
    <SectionPanel
      title="Speakers"
      count={event.speakers.length}
      ariaLabel="Speakers"
      editing={editing}
      saving={saving}
      error={error}
      onEdit={startEdit}
      onSave={save}
      onCancel={cancel}
      addLabel="Add speaker"
      onAdd={() => setRows((current) => [...current, blankRow()])}
      view={view}
      editor={editor}
    />
  );
}

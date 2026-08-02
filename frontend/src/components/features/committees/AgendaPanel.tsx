"use client";

import { useEffect, useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { updateMeeting } from "@/lib/api/committees";
import { AGENDA_ITEM_STATUSES, AGENDA_PRIORITIES } from "@/lib/committees/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import { useObjectDocuments } from "@/hooks/useObjectDocuments";
import { AgendaPriorityBadge, AgendaStatusBadge } from "./CommitteeBadges";
import type {
  AgendaItem,
  AgendaItemPriority,
  AgendaItemStatus,
  MeetingResponse,
} from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

interface AgendaRow {
  title: string;
  priority: AgendaItemPriority | "";
  presenter: string;
  discussion: string;
  decision: string;
  status: AgendaItemStatus | "";
  document_ids: string[];
}

function toRows(items: AgendaItem[]): AgendaRow[] {
  return items.map((item) => ({
    title: item.title ?? "",
    priority: item.priority ?? "",
    presenter: item.presenter ?? "",
    discussion: item.discussion ?? "",
    decision: item.decision ?? "",
    status: item.status ?? "",
    document_ids: item.document_ids ?? [],
  }));
}

/**
 * PART 4 agenda manager. Whole-list replace through `PUT /committees/meetings/{id}`
 * (the frozen merge contract) — a single explicit save keeps the audit clean.
 * Supporting-document options are the meeting's own linked documents (PART 6).
 */
export function AgendaPanel({
  meeting,
  onSaved,
  onError,
}: {
  meeting: MeetingResponse;
  onSaved: (meeting: MeetingResponse) => void;
  onError: (message: string) => void;
}) {
  const [rows, setRows] = useState<AgendaRow[]>(() => toRows(meeting.agenda_items));
  const [saving, setSaving] = useState(false);
  const { documents: documentOptions } = useObjectDocuments(meeting.id);

  // A refresh replaces the meeting payload — mirror it into the editor.
  useEffect(() => {
    setRows(toRows(meeting.agenda_items));
  }, [meeting.agenda_items]);

  const addRow = () =>
    setRows((current) => [
      ...current,
      {
        title: "",
        priority: "medium",
        presenter: "",
        discussion: "",
        decision: "",
        status: "pending",
        document_ids: [],
      },
    ]);

  const removeRow = (index: number) =>
    setRows((current) => current.filter((_, rowIndex) => rowIndex !== index));

  const patchRow = (index: number, patch: Partial<AgendaRow>) =>
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );

  const handleSave = async () => {
    if (saving) return;
    const incomplete = rows.find((row) => !row.title.trim());
    if (incomplete) {
      onError("Every agenda item needs a title (or remove the row).");
      return;
    }
    setSaving(true);
    try {
      const payload: AgendaItem[] = rows.map((row) => ({
        title: row.title.trim(),
        priority: row.priority || null,
        presenter: row.presenter.trim() || null,
        discussion: row.discussion.trim() || null,
        decision: row.decision.trim() || null,
        status: row.status || null,
        document_ids: row.document_ids,
      }));
      const updated = await updateMeeting(meeting.id, {
        agenda_items: payload,
        uploaded_by: meeting.uploaded_by || "faculty:ui",
      });
      onSaved(updated);
    } catch (err) {
      onError(toErrorMessage(err, "Could not save the agenda."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section
      aria-label="Agenda"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Agenda ({rows.length} item{rows.length === 1 ? "" : "s"})
        </h2>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={addRow}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add item
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-60"
          >
            {saving ? <Spinner className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" aria-hidden="true" />}
            {saving ? "Saving…" : "Save agenda"}
          </button>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No agenda items yet — add the first item to structure the meeting.
        </p>
      ) : (
        <ol className="space-y-3">
          {rows.map((row, index) => (
            <li
              key={index}
              className="rounded-lg border border-[var(--border-subtle)] p-3"
              aria-label={`Agenda item ${index + 1}`}
            >
              <div className="grid grid-cols-1 items-end gap-2 sm:grid-cols-[1fr_120px_130px_130px_auto]">
                <label className="block">
                  <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                    Title *
                  </span>
                  <input
                    type="text"
                    value={row.title}
                    onChange={(event) => patchRow(index, { title: event.target.value })}
                    aria-label={`Agenda item ${index + 1} title`}
                    placeholder="e.g. Approval of lab equipment quotes"
                    className={FIELD_CLASS}
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                    Priority
                  </span>
                  <select
                    value={row.priority}
                    onChange={(event) =>
                      patchRow(index, { priority: event.target.value as AgendaItemPriority | "" })
                    }
                    aria-label={`Agenda item ${index + 1} priority`}
                    className={FIELD_CLASS}
                  >
                    <option value="">—</option>
                    {AGENDA_PRIORITIES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                    Presenter
                  </span>
                  <input
                    type="text"
                    value={row.presenter}
                    onChange={(event) => patchRow(index, { presenter: event.target.value })}
                    aria-label={`Agenda item ${index + 1} presenter`}
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
                      patchRow(index, { status: event.target.value as AgendaItemStatus | "" })
                    }
                    aria-label={`Agenda item ${index + 1} status`}
                    className={FIELD_CLASS}
                  >
                    <option value="">—</option>
                    {AGENDA_ITEM_STATUSES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => removeRow(index)}
                  aria-label={`Remove agenda item ${index + 1}`}
                  className="rounded-lg p-2 text-[var(--danger)] transition-colors hover:bg-[var(--danger-subtle)]"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>

              <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                    Discussion
                  </span>
                  <textarea
                    value={row.discussion}
                    onChange={(event) => patchRow(index, { discussion: event.target.value })}
                    aria-label={`Agenda item ${index + 1} discussion`}
                    rows={2}
                    className={FIELD_CLASS}
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                    Decision
                  </span>
                  <textarea
                    value={row.decision}
                    onChange={(event) => patchRow(index, { decision: event.target.value })}
                    aria-label={`Agenda item ${index + 1} decision`}
                    rows={2}
                    className={FIELD_CLASS}
                  />
                </label>
              </div>

              {documentOptions.length > 0 ? (
                <label className="mt-2 block">
                  <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                    Supporting documents (linked to this meeting)
                  </span>
                  <select
                    multiple
                    value={row.document_ids}
                    onChange={(event) =>
                      patchRow(index, {
                        document_ids: Array.from(event.target.selectedOptions).map(
                          (option) => option.value,
                        ),
                      })
                    }
                    aria-label={`Agenda item ${index + 1} supporting documents`}
                    className={`${FIELD_CLASS} h-20`}
                  >
                    {documentOptions.map((document) => (
                      <option key={document.id} value={document.id}>
                        {document.title}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[var(--text-tertiary)]">
                {row.priority ? <AgendaPriorityBadge priority={row.priority} /> : null}
                {row.status ? <AgendaStatusBadge status={row.status} /> : null}
                {(row.document_ids ?? []).length > 0 ? (
                  <span>{row.document_ids.length} supporting document(s)</span>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

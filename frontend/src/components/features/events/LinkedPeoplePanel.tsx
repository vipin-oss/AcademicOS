"use client";

import { useState } from "react";
import Link from "next/link";
import { Pencil } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { updateEvent } from "@/lib/api/events";
import { Spinner } from "@/components/features/objects/Spinner";
import type { PickerOption } from "@/components/features/finance/SectionPanel";
import type { EventInputLinkGroup, EventResponse } from "@/types";

const MULTI_SELECT_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1.5 text-sm text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none h-36";

/**
 * PART 7 linked people — one link-group editor (faculty / students). The
 * links object is a WHOLE-links replace across every input group (the frozen
 * finance precedent), so the save re-sends every other group untouched and
 * swaps only this one. Chrome mirrors SectionPanel without an "add row"
 * button — the multi-select IS the add affordance.
 */
export function LinkedPeoplePanel({
  event,
  group,
  title,
  options,
  hrefFor,
  onUpdated,
}: {
  event: EventResponse;
  group: "faculty" | "students";
  title: string;
  options: PickerOption[];
  hrefFor: (id: string) => string;
  onUpdated: (event: EventResponse) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const items = event.links?.[group] ?? [];

  const startEdit = () => {
    setSelected(items.map((link) => link.id));
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setError(null);
  };

  const save = async () => {
    if (saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateEvent(event.id, {
        links: {
          faculty: (event.links?.faculty ?? []).map((link) => link.id),
          students: (event.links?.students ?? []).map((link) => link.id),
          projects: (event.links?.projects ?? []).map((link) => link.id),
          grants: (event.links?.grants ?? []).map((link) => link.id),
          committees: (event.links?.committees ?? []).map((link) => link.id),
          [group]: selected,
        } as Partial<Record<EventInputLinkGroup, string[]>>,
      });
      onUpdated(updated);
      setSaving(false);
      setEditing(false);
    } catch (err) {
      setSaving(false);
      setError(toErrorMessage(err));
    }
  };

  return (
    <section
      aria-label={title}
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          {title} ({items.length})
        </h2>
        {editing ? (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={cancel}
              disabled={saving}
              className="rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={save}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? <Spinner /> : null}
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={startEdit}
            aria-label={`Edit ${title.toLowerCase()}`}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <Pencil className="h-3.5 w-3.5" aria-hidden="true" /> Edit
          </button>
        )}
      </div>

      {editing ? (
        <div className="space-y-3">
          <label className="block">
            <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
              {title} linked to this event
            </span>
            <select
              multiple
              value={selected}
              onChange={(change) =>
                setSelected(
                  Array.from(change.target.selectedOptions).map((option) => option.value),
                )
              }
              aria-label={`Linked ${group}`}
              className={MULTI_SELECT_CLASS}
            >
              {options.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          {error ? (
            <p
              role="alert"
              className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
            >
              {error}
            </p>
          ) : null}
        </div>
      ) : items.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No linked {title.toLowerCase()} yet — edit to link them to this event.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((item) => (
            <li key={item.id}>
              <Link
                href={hrefFor(item.id)}
                className="text-sm text-[var(--accent)] hover:underline"
              >
                {item.title}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

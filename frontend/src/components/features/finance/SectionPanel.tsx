"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { Spinner } from "@/components/features/objects/Spinner";

/**
 * Shared chrome for the five metadata-section panels (quotations, comparative
 * statement, purchase orders, bills, assets) on the proposal workspace.
 * Each panel keeps its own row state; this shell provides the consistent
 * header (count + Edit/Save/Cancel) and the save-error alert.
 */
export function SectionPanel({
  title,
  count,
  ariaLabel,
  editing,
  saving,
  error,
  onEdit,
  onSave,
  onCancel,
  addLabel,
  onAdd,
  view,
  editor,
}: {
  title: string;
  count: number;
  ariaLabel: string;
  editing: boolean;
  saving: boolean;
  error: string | null;
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  /** Edit-mode "add row" affordance. */
  addLabel: string;
  onAdd: () => void;
  view: React.ReactNode;
  editor: React.ReactNode;
}) {
  return (
    <section
      aria-label={ariaLabel}
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          {title} ({count})
        </h2>
        {editing ? (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onCancel}
              disabled={saving}
              className="rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onSave}
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
            onClick={onEdit}
            aria-label={`Edit ${title.toLowerCase()}`}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <Pencil className="h-3.5 w-3.5" aria-hidden="true" /> Edit
          </button>
        )}
      </div>

      {editing ? (
        <div className="space-y-3">
          {editor}
          <button
            type="button"
            onClick={onAdd}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" /> {addLabel}
          </button>
          {error ? (
            <p
              role="alert"
              className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
            >
              {error}
            </p>
          ) : null}
        </div>
      ) : (
        view
      )}
    </section>
  );
}

export interface PickerOption {
  id: string;
  label: string;
}

const ROW_FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

/** One labelled input inside a section row editor. */
export function RowField({
  label,
  ariaLabel,
  children,
}: {
  label: string;
  ariaLabel?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
        {label}
      </span>
      {children}
    </label>
  );
}

export function RowTextInput({
  value,
  onChange,
  ariaLabel,
  placeholder,
  type = "text",
}: {
  value: string;
  onChange: (value: string) => void;
  ariaLabel: string;
  placeholder?: string;
  type?: "text" | "date" | "number";
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      aria-label={ariaLabel}
      placeholder={placeholder}
      className={ROW_FIELD_CLASS}
    />
  );
}

export function RowSelect({
  value,
  onChange,
  ariaLabel,
  options,
  emptyLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  ariaLabel: string;
  options: { value: string; label: string }[];
  emptyLabel: string;
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      aria-label={ariaLabel}
      className={ROW_FIELD_CLASS}
    >
      <option value="">{emptyLabel}</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

/** Multi-select of linked documents (documents integration, PART 10). */
export function RowDocumentsSelect({
  value,
  onChange,
  ariaLabel,
  options,
}: {
  value: string[];
  onChange: (ids: string[]) => void;
  ariaLabel: string;
  options: PickerOption[];
}) {
  return (
    <select
      multiple
      value={value}
      onChange={(event) =>
        onChange(Array.from(event.target.selectedOptions).map((option) => option.value))
      }
      aria-label={ariaLabel}
      className={`${ROW_FIELD_CLASS} h-20`}
    >
      {options.map((option) => (
        <option key={option.id} value={option.id}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

/** Remove-row affordance with a stable aria-label for tests. */
export function RemoveRowButton({
  onClick,
  ariaLabel,
}: {
  onClick: () => void;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      className="self-start rounded-lg p-2 text-[var(--danger)] transition-colors hover:bg-[var(--danger-subtle)]"
    >
      <Trash2 className="h-4 w-4" aria-hidden="true" />
    </button>
  );
}

/** Grid wrapper so every row editor shares the same responsive rhythm. */
export function RowGrid({ children }: { children: React.ReactNode }) {
  return (
    <li className="rounded-lg border border-[var(--border-subtle)] p-2">
      <div className="grid grid-cols-1 items-end gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {children}
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Wire helpers — keep only set keys (backend validators enforce whitelists).
// ---------------------------------------------------------------------------

/** Trimmed string or undefined (key omitted when empty). */
export function clean(value: string | null | undefined): string | undefined {
  const trimmed = (value ?? "").trim();
  return trimmed ? trimmed : undefined;
}

/** Parse a money input; returns undefined for blank, NaN for invalid. */
export function parseMoney(raw: string): number | undefined {
  const trimmed = raw.trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  return Number.isNaN(parsed) ? Number.NaN : parsed;
}

/** ₹ display for the view tables (strings come from metadata). */
export function moneyOf(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") return "—";
  const parsed = typeof raw === "number" ? raw : Number(raw);
  if (Number.isNaN(parsed)) return String(raw);
  return `₹${parsed.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

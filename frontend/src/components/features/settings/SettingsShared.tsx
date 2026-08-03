"use client";

/**
 * Shared primitives for the Settings & Preferences sections — the module's
 * own copy of the frozen form idioms (FIELD_CLASS from TaskModal/EventModal,
 * accent/ghost buttons, role="status"/"alert" planes). Every section card is
 * a labelled <section> with its own save bar, so each of the 8 sections maps
 * one-to-one onto `PUT /settings/{section}`.
 */
import { useEffect, useMemo, useState } from "react";

export const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

export const PRIMARY_BUTTON_CLASS =
  "rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60";

export const GHOST_BUTTON_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-60";

export const DANGER_BUTTON_CLASS =
  "rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-4 py-2 text-sm font-medium text-[var(--danger)] hover:bg-[var(--danger)] hover:text-white disabled:cursor-not-allowed disabled:opacity-60";

export interface Option {
  value: string;
  label: string;
}

export function SectionCard({
  title,
  description,
  badge,
  children,
  footer,
}: {
  title: string;
  description?: string;
  badge?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <section
      aria-label={title}
      className="space-y-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5"
    >
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">{title}</h2>
          {badge ? (
            <span className="rounded-full border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
              {badge}
            </span>
          ) : null}
        </div>
        {description ? (
          <p className="mt-1 text-sm text-[var(--text-secondary)]">{description}</p>
        ) : null}
      </div>
      {children}
      {footer}
    </section>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      {children}
      {hint ? <p className="mt-1 text-xs text-[var(--text-tertiary)]">{hint}</p> : null}
    </div>
  );
}

export function TextInput({
  ariaLabel,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  ariaLabel: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <input
      type={type}
      aria-label={ariaLabel}
      className={FIELD_CLASS}
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export function TextArea({
  ariaLabel,
  value,
  onChange,
  placeholder,
  rows = 4,
}: {
  ariaLabel: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <textarea
      aria-label={ariaLabel}
      className={FIELD_CLASS}
      rows={rows}
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export function SelectInput({
  ariaLabel,
  value,
  onChange,
  options,
}: {
  ariaLabel: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly Option[];
}) {
  // A value that is not in the catalogue (e.g. imported data) stays visible
  // and selectable instead of silently blanking the control.
  const resolved = useMemo(() => {
    if (options.some((option) => option.value === value)) return options;
    return [...options, { value, label: value || "— not set —" }];
  }, [options, value]);
  return (
    <select
      aria-label={ariaLabel}
      className={FIELD_CLASS}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      {resolved.map((option) => (
        <option key={option.value || "<empty>"} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

export function NumberInput({
  ariaLabel,
  value,
  onChange,
  min,
  max,
}: {
  ariaLabel: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
}) {
  return (
    <input
      type="number"
      aria-label={ariaLabel}
      className={FIELD_CLASS}
      value={Number.isFinite(value) ? value : ""}
      min={min}
      max={max}
      onChange={(event) => onChange(Number.parseInt(event.target.value, 10))}
    />
  );
}

export function Toggle({
  ariaLabel,
  checked,
  onChange,
  label,
  hint,
}: {
  ariaLabel: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  hint?: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-3 py-2.5">
      <input
        type="checkbox"
        aria-label={ariaLabel}
        className="mt-0.5 h-4 w-4 accent-[var(--accent)]"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>
        <span className="block text-sm font-medium text-[var(--text-primary)]">{label}</span>
        {hint ? (
          <span className="mt-0.5 block text-xs text-[var(--text-tertiary)]">{hint}</span>
        ) : null}
      </span>
    </label>
  );
}

export function ChecklistOption({
  ariaLabel,
  checked,
  onChange,
  label,
}: {
  ariaLabel: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-3 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-hover)]">
      <input
        type="checkbox"
        aria-label={ariaLabel}
        className="h-4 w-4 accent-[var(--accent)]"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  );
}

/**
 * Draft of one section's values, re-synced whenever the authoritative
 * values change (initial load, save result, import, reset). `dirty` is a
 * deep JSON comparison — field edits therefore enable/disable Save exactly.
 */
export function useSyncedDraft<T>(values: T) {
  const [draft, setDraft] = useState(values);
  useEffect(() => {
    setDraft(values);
  }, [values]);
  const dirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(values),
    [draft, values],
  );
  const update = (patch: Partial<T>) => setDraft((prev) => ({ ...prev, ...patch }));
  return { draft, update, dirty };
}

/** Save button + status/error plane used by every section footer. */
export function SaveBar({
  saveAriaLabel,
  statusAriaLabel,
  saving,
  saved,
  error,
  disabled,
  onSave,
}: {
  saveAriaLabel: string;
  statusAriaLabel: string;
  saving: boolean;
  saved: boolean;
  error: string | null;
  disabled?: boolean;
  onSave: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-t border-[var(--border-subtle)] pt-4">
      <button
        type="button"
        aria-label={saveAriaLabel}
        className={PRIMARY_BUTTON_CLASS}
        disabled={saving || disabled}
        onClick={onSave}
      >
        {saving ? "Saving…" : "Save changes"}
      </button>
      <span
        role="status"
        aria-live="polite"
        aria-label={statusAriaLabel}
        className="text-sm text-[var(--success)]"
      >
        {saved && !error ? "Saved." : ""}
      </span>
      {error ? (
        <span role="alert" className="text-sm text-[var(--danger)]">
          {error}
        </span>
      ) : null}
    </div>
  );
}

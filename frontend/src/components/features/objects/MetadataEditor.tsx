"use client";

import type { Dispatch, SetStateAction } from "react";
import { Plus, Trash2 } from "lucide-react";
import { DEPARTMENT_METADATA_KEY } from "@/lib/objects/constants";
import { cn } from "@/lib/utils";
import type { MetadataFieldPayload } from "@/types";

export interface MetaRow {
  key: string;
  value: string;
}

export interface MetadataValidation {
  /** index -> message, rendered under the offending row. */
  rowErrors: Record<number, string>;
  /** First blocking problem, or null when the rows are safe to submit. */
  error: string | null;
}

/**
 * Validation rules (single source of truth for the editor AND the modal):
 *  - a key is required as soon as the row has a value;
 *  - keys are unique, case-insensitively;
 *  - `department` is reserved — it is owned by the Department field, so it can
 *    never be duplicated as a free-form row.
 */
export function validateMetadataRows(
  rows: MetaRow[],
  reservedKeys: string[] = [DEPARTMENT_METADATA_KEY],
): MetadataValidation {
  const rowErrors: Record<number, string> = {};
  const seen = new Map<string, number>();
  const reserved = reservedKeys.map((key) => key.toLowerCase());

  rows.forEach((row, index) => {
    const key = row.key.trim();
    const value = row.value.trim();
    const normalised = key.toLowerCase();

    if (!key) {
      if (value) rowErrors[index] = "A key is required for this value.";
      return;
    }
    if (reserved.includes(normalised)) {
      rowErrors[index] = `"${key}" is reserved — use the Department field above.`;
      return;
    }
    if (seen.has(normalised)) {
      rowErrors[index] = `Duplicate key "${key}".`;
      return;
    }
    seen.set(normalised, index);
  });

  const firstError = Object.keys(rowErrors)
    .map(Number)
    .sort((a, b) => a - b)
    .map((index) => rowErrors[index])[0];

  return { rowErrors, error: firstError ?? null };
}

/** Drop empty rows and trim — what actually goes on the wire. */
export function metadataRowsToPayload(rows: MetaRow[]): MetadataFieldPayload[] {
  return rows
    .filter((row) => row.key.trim().length > 0)
    .map((row) => ({ key: row.key.trim(), value: row.value.trim() }));
}

/** `Record<string, string>` (API shape) -> editor rows, department excluded. */
export function metadataToRows(
  metadata: Record<string, string> | null | undefined,
  excludeKeys: string[] = [DEPARTMENT_METADATA_KEY],
): MetaRow[] {
  const excluded = excludeKeys.map((key) => key.toLowerCase());
  return Object.entries(metadata ?? {})
    .filter(([key]) => !excluded.includes(key.toLowerCase()))
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => ({ key, value }));
}

export function MetadataEditor({
  rows,
  onChange,
  disabled = false,
  validation,
}: {
  rows: MetaRow[];
  /** Accepts a React state setter — updates are functional, so two edits in
   *  the same batch can never drop one another. */
  onChange: Dispatch<SetStateAction<MetaRow[]>>;
  disabled?: boolean;
  validation?: MetadataValidation;
}) {
  const rowErrors = validation?.rowErrors ?? {};

  const addRow = () => onChange((current) => [...current, { key: "", value: "" }]);
  const updateRow = (index: number, patch: Partial<MetaRow>) =>
    onChange((current) => current.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  const removeRow = (index: number) =>
    onChange((current) => current.filter((_, i) => i !== index));

  const inputClass = (invalid: boolean) =>
    cn(
      "w-full rounded-lg border bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none disabled:opacity-60",
      invalid
        ? "border-[var(--danger)] focus:border-[var(--danger)]"
        : "border-[var(--border-subtle)] focus:border-[var(--accent)]",
    );

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-[var(--text-secondary)]">Metadata</span>
        <button
          type="button"
          onClick={addRow}
          disabled={disabled}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-[var(--accent)] transition-colors hover:bg-[var(--accent-subtle)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add row
        </button>
      </div>

      {rows.length === 0 ? (
        <p className="rounded-lg border border-dashed border-[var(--border-strong)] px-3 py-3 text-xs text-[var(--text-tertiary)]">
          No metadata yet. Add key/value pairs to enrich this object.
        </p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row, index) => {
            const invalid = Boolean(rowErrors[index]);
            return (
              <li key={index}>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
                  <div className="sm:w-1/3">
                    <input
                      value={row.key}
                      onChange={(event) => updateRow(index, { key: event.target.value })}
                      placeholder="key"
                      disabled={disabled}
                      aria-label={`Metadata key ${index + 1}`}
                      aria-invalid={invalid}
                      className={inputClass(invalid)}
                    />
                  </div>
                  <div className="flex flex-1 items-start gap-2">
                    <input
                      value={row.value}
                      onChange={(event) => updateRow(index, { value: event.target.value })}
                      placeholder="value"
                      disabled={disabled}
                      aria-label={`Metadata value ${index + 1}`}
                      className={inputClass(false)}
                    />
                    <button
                      type="button"
                      onClick={() => removeRow(index)}
                      disabled={disabled}
                      aria-label={`Remove metadata row ${index + 1}`}
                      className="mt-0.5 rounded-md p-2 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--danger)] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                </div>
                {invalid ? (
                  <p className="mt-1 text-xs text-[var(--danger)]">{rowErrors[index]}</p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

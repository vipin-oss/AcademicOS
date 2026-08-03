"use client";

/**
 * PART 7 — Search preferences: default scope, recent-searches limit
 * (0–50, validated server-side) and saved filters as a small JSON map (empty
 * object = none). Free-form module keys are allowed by the backend.
 */
import { useEffect, useMemo, useState } from "react";

import { toErrorMessage } from "@/lib/api/client";
import { RECENT_SEARCHES_MAX, RECENT_SEARCHES_MIN, SEARCH_SCOPES } from "@/lib/settings/constants";
import type { SearchPrefsSection as SearchValues } from "@/types";
import {
  Field,
  NumberInput,
  SaveBar,
  SectionCard,
  SelectInput,
  TextArea,
  useSyncedDraft,
} from "./SettingsShared";

function canonical(filters: Record<string, unknown>): string {
  return JSON.stringify(filters, null, 2);
}

export function SearchPrefsSection({
  values,
  onSave,
}: {
  values: SearchValues;
  onSave: (values: SearchValues) => Promise<void>;
}) {
  const { draft, update, dirty } = useSyncedDraft(values);
  const [filtersText, setFiltersText] = useState(() => canonical(values.saved_filters));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setFiltersText(canonical(values.saved_filters));
  }, [values.saved_filters]);

  const filtersDirty = useMemo(
    () => filtersText.trim() !== canonical(values.saved_filters).trim(),
    [filtersText, values.saved_filters],
  );
  const anyDirty = dirty || filtersDirty;

  const handleSave = async () => {
    if (saving) return;
    setError(null);
    setSaved(false);
    if (
      !Number.isFinite(draft.recent_searches_limit) ||
      draft.recent_searches_limit < RECENT_SEARCHES_MIN ||
      draft.recent_searches_limit > RECENT_SEARCHES_MAX
    ) {
      setError(`Recent searches limit must be between ${RECENT_SEARCHES_MIN} and ${RECENT_SEARCHES_MAX}.`);
      return;
    }
    let filters: Record<string, unknown>;
    const text = filtersText.trim();
    try {
      const parsed: unknown = text ? JSON.parse(text) : {};
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("not-a-map");
      }
      filters = parsed as Record<string, unknown>;
    } catch {
      setError('Saved filters must be a JSON object, e.g. {"status": "active"}.');
      return;
    }
    setSaving(true);
    try {
      await onSave({ ...draft, saved_filters: filters });
      setSaved(true);
    } catch (err) {
      setError(toErrorMessage(err, "Could not save the search preferences."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SectionCard
      title="Search preferences"
      description="Where global search looks first, how many recent searches are remembered, and any filters you want to keep around."
      footer={
        <SaveBar
          saveAriaLabel="Save search preferences"
          statusAriaLabel="Search status"
          saving={saving}
          saved={saved}
          error={error}
          disabled={!anyDirty}
          onSave={handleSave}
        />
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Default search scope">
          <SelectInput
            ariaLabel="Default search scope"
            value={draft.default_scope}
            options={SEARCH_SCOPES}
            onChange={(value) => {
              setSaved(false);
              setError(null);
              update({ default_scope: value });
            }}
          />
        </Field>
        <Field label="Recent searches limit" hint={`0 to ${RECENT_SEARCHES_MAX} — 0 disables recent searches.`}>
          <NumberInput
            ariaLabel="Recent searches limit"
            value={draft.recent_searches_limit}
            min={RECENT_SEARCHES_MIN}
            max={RECENT_SEARCHES_MAX}
            onChange={(value) => {
              setSaved(false);
              setError(null);
              update({ recent_searches_limit: value });
            }}
          />
        </Field>
      </div>
      <Field label="Saved filters" hint='A JSON object of filter presets, e.g. {"objects": {"status": "active"}}.'>
        <TextArea
          ariaLabel="Saved filters"
          value={filtersText}
          rows={4}
          placeholder="{}"
          onChange={(value) => {
            setSaved(false);
            setError(null);
            setFiltersText(value);
          }}
        />
      </Field>
    </SectionCard>
  );
}

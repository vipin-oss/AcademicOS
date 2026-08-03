"use client";

/**
 * PART 8 — Privacy: local + session preferences only. These toggles decide
 * what the UI may remember on this device (last module, filters, page size)
 * and honour reduced motion. No authentication or session redesign here.
 */
import { useState } from "react";

import { toErrorMessage } from "@/lib/api/client";
import { SESSION_PAGE_SIZES } from "@/lib/settings/constants";
import type { PrivacySection as PrivacyValues } from "@/types";
import { Field, SaveBar, SectionCard, SelectInput, Toggle, useSyncedDraft } from "./SettingsShared";

export function PrivacySection({
  values,
  onSave,
}: {
  values: PrivacyValues;
  onSave: (values: PrivacyValues) => Promise<void>;
}) {
  const { draft, update, dirty } = useSyncedDraft(values);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const edit = (patch: Partial<PrivacyValues>) => {
    setSaved(false);
    setError(null);
    update(patch);
  };

  const handleSave = async () => {
    if (saving) return;
    setError(null);
    setSaved(false);
    if (!Number.isFinite(draft.session_page_size) || draft.session_page_size < 1 || draft.session_page_size > 200) {
      setError("Session page size must be between 1 and 200.");
      return;
    }
    setSaving(true);
    try {
      await onSave(draft);
      setSaved(true);
    } catch (err) {
      setError(toErrorMessage(err, "Could not save the privacy preferences."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SectionCard
      title="Privacy"
      description="What AcademicOS may remember on this device. All of it is local/session convenience — clearing your browser data removes it."
      footer={
        <SaveBar
          saveAriaLabel="Save privacy preferences"
          statusAriaLabel="Privacy status"
          saving={saving}
          saved={saved}
          error={error}
          disabled={!dirty}
          onSave={handleSave}
        />
      }
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Toggle
          ariaLabel="Remember last module"
          label="Remember the last module"
          hint="Reopen the module you used most recently."
          checked={draft.remember_last_module}
          onChange={(checked) => edit({ remember_last_module: checked })}
        />
        <Toggle
          ariaLabel="Session filter memory"
          label="Remember session filters"
          hint="Keep list filters while you move between pages in this session."
          checked={draft.session_filter_memory}
          onChange={(checked) => edit({ session_filter_memory: checked })}
        />
        <Toggle
          ariaLabel="Reduce motion"
          label="Reduce motion"
          hint="Minimise animations and transitions for accessibility."
          checked={draft.reduce_motion}
          onChange={(checked) => edit({ reduce_motion: checked })}
        />
        <Field label="Session page size" hint="Default rows per page for lists in this session (1–200).">
          <SelectInput
            ariaLabel="Session page size"
            value={String(draft.session_page_size)}
            options={SESSION_PAGE_SIZES.map((size) => ({ value: String(size), label: `${size} rows` }))}
            onChange={(value) => edit({ session_page_size: Number.parseInt(value, 10) })}
          />
        </Field>
      </div>
    </SectionCard>
  );
}

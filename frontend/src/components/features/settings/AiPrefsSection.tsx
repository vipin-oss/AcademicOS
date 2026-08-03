"use client";

/**
 * PART 10 — Future-ready preferences: preferred writing style, report format
 * and dashboard layout. Stored in the settings document so future AI /
 * personalization features can read them — nothing in the current app
 * consumes them yet, and this module implements no AI functionality.
 */
import { useState } from "react";

import { toErrorMessage } from "@/lib/api/client";
import { AI_LAYOUTS, AI_REPORT_FORMATS } from "@/lib/settings/constants";
import type { AiPrefsSection as AiValues } from "@/types";
import { Field, SaveBar, SectionCard, SelectInput, TextInput, useSyncedDraft } from "./SettingsShared";

export function AiPrefsSection({
  values,
  onSave,
}: {
  values: AiValues;
  onSave: (values: AiValues) => Promise<void>;
}) {
  const { draft, update, dirty } = useSyncedDraft(values);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const edit = (patch: Partial<AiValues>) => {
    setSaved(false);
    setError(null);
    update(patch);
  };

  const handleSave = async () => {
    if (saving) return;
    setError(null);
    setSaved(false);
    setSaving(true);
    try {
      await onSave(draft);
      setSaved(true);
    } catch (err) {
      setError(toErrorMessage(err, "Could not save the personalization preferences."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SectionCard
      title="AI & personalization"
      badge="Stored for future use — inactive"
      description="Preferences future AI features will honour when they arrive. AcademicOS does not implement AI here — these values are simply stored."
      footer={
        <SaveBar
          saveAriaLabel="Save AI preferences"
          statusAriaLabel="AI status"
          saving={saving}
          saved={saved}
          error={error}
          disabled={!dirty}
          onSave={handleSave}
        />
      }
    >
      <Field label="Preferred writing style" hint="e.g. formal, concise, bullet points.">
        <TextInput
          ariaLabel="Preferred writing style"
          value={draft.preferred_writing_style}
          placeholder="e.g. concise and formal"
          onChange={(value) => edit({ preferred_writing_style: value })}
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Preferred report format">
          <SelectInput
            ariaLabel="Preferred report format"
            value={draft.preferred_report_format}
            options={AI_REPORT_FORMATS}
            onChange={(value) => edit({ preferred_report_format: value })}
          />
        </Field>
        <Field label="Preferred dashboard layout">
          <SelectInput
            ariaLabel="Preferred dashboard layout"
            value={draft.preferred_dashboard_layout}
            options={AI_LAYOUTS}
            onChange={(value) => edit({ preferred_dashboard_layout: value })}
          />
        </Field>
      </div>
    </SectionCard>
  );
}

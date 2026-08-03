"use client";

/**
 * PART 3 — Academic defaults: default session / department / programme /
 * semester, timezone (curated IANA list — the backend stores any string) and
 * date format. These are defaults the UI may prefill elsewhere; saving here
 * never rewrites module data.
 */
import { useState } from "react";

import { toErrorMessage } from "@/lib/api/client";
import { DATE_FORMATS, TIMEZONES } from "@/lib/settings/constants";
import type { AcademicSection as AcademicValues } from "@/types";
import { Field, SaveBar, SectionCard, SelectInput, TextInput, useSyncedDraft } from "./SettingsShared";

export function AcademicSection({
  values,
  onSave,
}: {
  values: AcademicValues;
  onSave: (values: AcademicValues) => Promise<void>;
}) {
  const { draft, update, dirty } = useSyncedDraft(values);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const edit = (patch: Partial<AcademicValues>) => {
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
      setError(toErrorMessage(err, "Could not save the academic defaults."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SectionCard
      title="Academic defaults"
      description="Prefill defaults for new academic work — session, department, programme, semester — plus your timezone and preferred date format."
      footer={
        <SaveBar
          saveAriaLabel="Save academic defaults"
          statusAriaLabel="Academic status"
          saving={saving}
          saved={saved}
          error={error}
          disabled={!dirty}
          onSave={handleSave}
        />
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Default session">
          <TextInput
            ariaLabel="Academic default session"
            value={draft.default_session}
            placeholder="e.g. 2025-26"
            onChange={(value) => edit({ default_session: value })}
          />
        </Field>
        <Field label="Default department">
          <TextInput
            ariaLabel="Academic default department"
            value={draft.default_department}
            placeholder="e.g. Computer Science"
            onChange={(value) => edit({ default_department: value })}
          />
        </Field>
        <Field label="Default programme">
          <TextInput
            ariaLabel="Academic default programme"
            value={draft.default_programme}
            placeholder="e.g. B.Sc. (Hons.)"
            onChange={(value) => edit({ default_programme: value })}
          />
        </Field>
        <Field label="Default semester">
          <TextInput
            ariaLabel="Academic default semester"
            value={draft.default_semester}
            placeholder="e.g. Semester 3"
            onChange={(value) => edit({ default_semester: value })}
          />
        </Field>
        <Field label="Timezone" hint="Used when displaying dates and times to you.">
          <SelectInput
            ariaLabel="Academic timezone"
            value={draft.default_timezone}
            options={TIMEZONES}
            onChange={(value) => edit({ default_timezone: value })}
          />
        </Field>
        <Field label="Date format">
          <SelectInput
            ariaLabel="Academic date format"
            value={draft.date_format}
            options={DATE_FORMATS}
            onChange={(value) => edit({ date_format: value })}
          />
        </Field>
      </div>
    </SectionCard>
  );
}

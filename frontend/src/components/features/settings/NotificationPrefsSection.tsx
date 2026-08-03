"use client";

/**
 * PART 4 — Notification preferences: master toggle, default reminder timing,
 * default priority, default calendar view and default calendar sources. These
 * are in-app defaults only — AcademicOS sends no email or push notifications.
 */
import { useState } from "react";

import { toErrorMessage } from "@/lib/api/client";
import {
  CALENDAR_SOURCE_OPTIONS,
  CALENDAR_VIEW_DEFAULTS,
  PRIORITY_DEFAULTS,
  REMINDER_DEFAULTS,
} from "@/lib/settings/constants";
import type { NotificationPrefsSection as NotificationValues } from "@/types";
import {
  ChecklistOption,
  Field,
  SaveBar,
  SectionCard,
  SelectInput,
  Toggle,
  useSyncedDraft,
} from "./SettingsShared";

export function NotificationPrefsSection({
  values,
  onSave,
}: {
  values: NotificationValues;
  onSave: (values: NotificationValues) => Promise<void>;
}) {
  const { draft, update, dirty } = useSyncedDraft(values);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const edit = (patch: Partial<NotificationValues>) => {
    setSaved(false);
    setError(null);
    update(patch);
  };

  const toggleSource = (source: string, checked: boolean) => {
    const next = checked
      ? [...draft.calendar_default_sources, source]
      : draft.calendar_default_sources.filter((item) => item !== source);
    edit({ calendar_default_sources: CALENDAR_SOURCE_OPTIONS.map((option) => option.value).filter((code) => next.includes(code)) });
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
      setError(toErrorMessage(err, "Could not save the notification preferences."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SectionCard
      title="Notification preferences"
      description="Defaults for in-app notifications and the calendar. AcademicOS does not send email or push notifications — these stay inside the app."
      footer={
        <SaveBar
          saveAriaLabel="Save notification preferences"
          statusAriaLabel="Notifications status"
          saving={saving}
          saved={saved}
          error={error}
          disabled={!dirty}
          onSave={handleSave}
        />
      }
    >
      <Toggle
        ariaLabel="Notifications enabled"
        label="Enable notifications"
        hint="When off, the notification center stops surfacing new items."
        checked={draft.enabled}
        onChange={(checked) => edit({ enabled: checked })}
      />
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Default reminder" hint="Applied to new tasks and deadlines.">
          <SelectInput
            ariaLabel="Default reminder"
            value={draft.reminder_default}
            options={REMINDER_DEFAULTS}
            onChange={(value) => edit({ reminder_default: value })}
          />
        </Field>
        <Field label="Default priority">
          <SelectInput
            ariaLabel="Default priority"
            value={draft.priority_default}
            options={PRIORITY_DEFAULTS}
            onChange={(value) => edit({ priority_default: value })}
          />
        </Field>
        <Field label="Default calendar view">
          <SelectInput
            ariaLabel="Default calendar view"
            value={draft.calendar_default_view}
            options={CALENDAR_VIEW_DEFAULTS}
            onChange={(value) => edit({ calendar_default_view: value })}
          />
        </Field>
      </div>
      <Field
        label="Default calendar sources"
        hint="Which feeds the calendar shows when you open it. None selected behaves like “all sources”."
      >
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {CALENDAR_SOURCE_OPTIONS.map((option) => (
            <ChecklistOption
              key={option.value}
              ariaLabel={`Default calendar source ${option.label}`}
              label={option.label}
              checked={draft.calendar_default_sources.includes(option.value)}
              onChange={(checked) => toggleSource(option.value, checked)}
            />
          ))}
        </div>
      </Field>
    </SectionCard>
  );
}

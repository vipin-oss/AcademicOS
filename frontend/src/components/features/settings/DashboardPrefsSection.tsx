"use client";

/**
 * PART 5 — Dashboard preferences: default landing page, favorite modules,
 * widget visibility and default view. Stored preferences only — this module
 * deliberately does not redesign or rebuild the dashboard itself.
 */
import { useState } from "react";

import { toErrorMessage } from "@/lib/api/client";
import { DASHBOARD_VIEWS, LANDING_PAGES, MODULE_OPTIONS, WIDGET_OPTIONS } from "@/lib/settings/constants";
import type { DashboardPrefsSection as DashboardValues } from "@/types";
import {
  ChecklistOption,
  Field,
  SaveBar,
  SectionCard,
  SelectInput,
  useSyncedDraft,
} from "./SettingsShared";

export function DashboardPrefsSection({
  values,
  onSave,
}: {
  values: DashboardValues;
  onSave: (values: DashboardValues) => Promise<void>;
}) {
  const { draft, update, dirty } = useSyncedDraft(values);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const edit = (patch: Partial<DashboardValues>) => {
    setSaved(false);
    setError(null);
    update(patch);
  };

  const toggleModule = (module: string, checked: boolean) => {
    const next = checked
      ? [...draft.favorite_modules, module]
      : draft.favorite_modules.filter((item) => item !== module);
    edit({
      favorite_modules: MODULE_OPTIONS.map((option) => option.value).filter((code) =>
        next.includes(code),
      ),
    });
  };

  const toggleWidget = (widget: string, checked: boolean) => {
    edit({ widget_visibility: { ...draft.widget_visibility, [widget]: checked } });
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
      setError(toErrorMessage(err, "Could not save the dashboard preferences."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SectionCard
      title="Dashboard preferences"
      description="How your dashboard should look and where the app should land. These preferences are stored for the dashboard to read — the dashboard layout itself is unchanged."
      footer={
        <SaveBar
          saveAriaLabel="Save dashboard preferences"
          statusAriaLabel="Dashboard status"
          saving={saving}
          saved={saved}
          error={error}
          disabled={!dirty}
          onSave={handleSave}
        />
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Default landing page" hint="The first page shown after the app loads.">
          <SelectInput
            ariaLabel="Default landing page"
            value={draft.default_landing_page}
            options={LANDING_PAGES}
            onChange={(value) => edit({ default_landing_page: value })}
          />
        </Field>
        <Field label="Default view">
          <SelectInput
            ariaLabel="Default dashboard view"
            value={draft.default_view}
            options={DASHBOARD_VIEWS}
            onChange={(value) => edit({ default_view: value })}
          />
        </Field>
      </div>
      <Field label="Favorite modules" hint="Pinned for quick access.">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {MODULE_OPTIONS.map((option) => (
            <ChecklistOption
              key={option.value}
              ariaLabel={`Favorite module ${option.label}`}
              label={option.label}
              checked={draft.favorite_modules.includes(option.value)}
              onChange={(checked) => toggleModule(option.value, checked)}
            />
          ))}
        </div>
      </Field>
      <Field label="Widget visibility" hint="Unchecked widgets stay hidden on the dashboard.">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {WIDGET_OPTIONS.map((option) => (
            <ChecklistOption
              key={option.value}
              ariaLabel={`Widget ${option.label}`}
              label={option.label}
              checked={draft.widget_visibility[option.value] ?? true}
              onChange={(checked) => toggleWidget(option.value, checked)}
            />
          ))}
        </div>
      </Field>
    </SectionCard>
  );
}

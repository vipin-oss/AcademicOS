"use client";

/**
 * PART 2 — Appearance: Light / Dark / System as radio cards. Saving applies
 * the theme immediately through the theme engine (toggles the `.dark` class
 * on <html>; "system" keeps a live OS listener). `custom_theme` is stored
 * for future user-defined themes and is intentionally not applied anywhere.
 */
import { useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

import { toErrorMessage } from "@/lib/api/client";
import { THEMES } from "@/lib/settings/constants";
import { applyThemePreference, toThemePreference } from "@/lib/settings/theme";
import type { AppearanceSection as AppearanceValues } from "@/types";
import { cn } from "@/lib/utils";
import { Field, SaveBar, SectionCard, TextInput, useSyncedDraft } from "./SettingsShared";

const THEME_ICONS = { light: Sun, dark: Moon, system: Monitor } as const;

export function AppearanceSection({
  values,
  onSave,
}: {
  values: AppearanceValues;
  onSave: (values: AppearanceValues) => Promise<void>;
}) {
  const { draft, update, dirty } = useSyncedDraft(values);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (saving) return;
    setError(null);
    setSaved(false);
    setSaving(true);
    try {
      await onSave(draft);
      applyThemePreference(toThemePreference(draft.theme));
      setSaved(true);
    } catch (err) {
      setError(toErrorMessage(err, "Could not save the appearance preferences."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SectionCard
      title="Appearance"
      description="Choose how AcademicOS looks on this device. Custom theme support is planned — a saved name is stored for when themes land."
      footer={
        <SaveBar
          saveAriaLabel="Save appearance"
          statusAriaLabel="Appearance status"
          saving={saving}
          saved={saved}
          error={error}
          disabled={!dirty}
          onSave={handleSave}
        />
      }
    >
      <div role="radiogroup" aria-label="Theme" className="grid gap-3 sm:grid-cols-3">
        {THEMES.map((option) => {
          const Icon = THEME_ICONS[option.value];
          const selected = draft.theme === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={`Theme ${option.value}`}
              className={cn(
                "flex items-start gap-3 rounded-xl border p-3 text-left transition-colors",
                selected
                  ? "border-[var(--accent)] bg-[var(--accent-subtle)]"
                  : "border-[var(--border-subtle)] bg-[var(--bg-surface-2)] hover:bg-[var(--bg-hover)]",
              )}
              onClick={() => {
                setSaved(false);
                setError(null);
                update({ theme: option.value });
              }}
            >
              <Icon className="mt-0.5 h-5 w-5 text-[var(--text-secondary)]" />
              <span>
                <span className="block text-sm font-medium text-[var(--text-primary)]">
                  {option.label}
                </span>
                <span className="mt-0.5 block text-xs text-[var(--text-tertiary)]">
                  {option.description}
                </span>
              </span>
            </button>
          );
        })}
      </div>
      <Field
        label="Custom theme name"
        hint="Future-ready only — stored now, applied when custom themes are introduced."
      >
        <TextInput
          ariaLabel="Appearance custom theme"
          value={draft.custom_theme}
          placeholder="e.g. Ocean (not applied yet)"
          onChange={(value) => {
            setSaved(false);
            setError(null);
            update({ custom_theme: value });
          }}
        />
      </Field>
    </SectionCard>
  );
}

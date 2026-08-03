"use client";

/**
 * Settings & Preferences workspace: loads the settings document once (the
 * backend materialises defaults on first touch) and renders the 8 section
 * cards + backup. Each section owns its draft and saves through the shared
 * `useSettings` hook (verbatim-merge PUT per section).
 */
import { useState } from "react";

import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { useSettings } from "@/hooks/useSettings";
import type { SettingsSectionCode, SettingsSections } from "@/types";
import { AcademicSection } from "./AcademicSection";
import { AiPrefsSection } from "./AiPrefsSection";
import { AppearanceSection } from "./AppearanceSection";
import { BackupSection } from "./BackupSection";
import { DashboardPrefsSection } from "./DashboardPrefsSection";
import { NotificationPrefsSection } from "./NotificationPrefsSection";
import { PrivacySection } from "./PrivacySection";
import { ProfileSection } from "./ProfileSection";
import { SearchPrefsSection } from "./SearchPrefsSection";

export function SettingsWorkspace() {
  const { settings, setSettings, loading, error, refresh, saveSection } = useSettings();
  const [photoTick, setPhotoTick] = useState(0);

  const makeSaver =
    <K extends SettingsSectionCode>(section: K) =>
    async (values: Partial<SettingsSections[K]>) => {
      await saveSection(section, values);
    };

  const handlePhotoChanged = () => {
    setPhotoTick((tick) => tick + 1);
    refresh({ silent: true });
  };

  if (loading) {
    return (
      <div className="space-y-6" aria-label="Settings loading" aria-busy="true">
        {Array.from({ length: 4 }).map((_, index) => (
          <CardSkeleton key={index} />
        ))}
      </div>
    );
  }

  if (error || !settings) {
    return (
      <div className="space-y-3">
        <p
          role="alert"
          className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
        >
          {error ?? "Could not load your settings."}
        </p>
        <button
          type="button"
          aria-label="Retry loading settings"
          className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
          onClick={() => void refresh()}
        >
          Try again
        </button>
      </div>
    );
  }

  const sections = settings.sections;

  return (
    <div className="space-y-6">
      <ProfileSection
        values={sections.profile}
        hasPhoto={settings.has_photo}
        photoName={settings.photo_name}
        photoVersion={`${settings.updated_at ?? "fresh"}:${photoTick}`}
        onSave={makeSaver("profile")}
        onPhotoChanged={handlePhotoChanged}
      />
      <AppearanceSection values={sections.appearance} onSave={makeSaver("appearance")} />
      <AcademicSection values={sections.academic} onSave={makeSaver("academic")} />
      <NotificationPrefsSection
        values={sections.notifications}
        onSave={makeSaver("notifications")}
      />
      <DashboardPrefsSection values={sections.dashboard} onSave={makeSaver("dashboard")} />
      <SearchPrefsSection values={sections.search} onSave={makeSaver("search")} />
      <PrivacySection values={sections.privacy} onSave={makeSaver("privacy")} />
      <AiPrefsSection values={sections.ai} onSave={makeSaver("ai")} />
      <BackupSection onImported={setSettings} />
    </div>
  );
}

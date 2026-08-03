"use client";

/**
 * PART 6 — Backup & restore (settings only): export the settings document as
 * a portable JSON file, import it back (replaces only the sections present in
 * the file), or reset every section to factory defaults. This is NOT a
 * database backup — no module records are touched.
 */
import { useRef, useState } from "react";

import { toErrorMessage } from "@/lib/api/client";
import { exportSettings, importSettings, resetSettings } from "@/lib/api/settings";
import type { SettingsDocument, SettingsSections } from "@/types";
import { DANGER_BUTTON_CLASS, GHOST_BUTTON_CLASS, SectionCard } from "./SettingsShared";

const EXPORT_FILE_NAME = "academicos-settings.json";

function extractSections(payload: unknown): Partial<SettingsSections> | null {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null;
  const record = payload as Record<string, unknown>;
  const candidate =
    record.sections && typeof record.sections === "object" && !Array.isArray(record.sections)
      ? (record.sections as Record<string, unknown>)
      : record;
  const sections: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(candidate)) {
    if (value && typeof value === "object" && !Array.isArray(value)) sections[key] = value;
  }
  return Object.keys(sections).length > 0 ? (sections as Partial<SettingsSections>) : null;
}

export function BackupSection({
  onImported,
}: {
  onImported: (doc: SettingsDocument) => void;
}) {
  const [busy, setBusy] = useState<"export" | "import" | "reset" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const clear = () => {
    setMessage(null);
    setError(null);
  };

  const handleExport = async () => {
    if (busy) return;
    clear();
    setBusy("export");
    try {
      const data = await exportSettings();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = EXPORT_FILE_NAME;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage(`Exported settings to ${EXPORT_FILE_NAME}.`);
    } catch (err) {
      setError(toErrorMessage(err, "Could not export the settings."));
    } finally {
      setBusy(null);
    }
  };

  const handleImportFile = async (file: File | undefined) => {
    if (!file || busy) return;
    clear();
    let sections: Partial<SettingsSections> | null = null;
    try {
      sections = extractSections(JSON.parse(await file.text()));
    } catch {
      sections = null;
    }
    if (!sections) {
      setError("That file is not a valid AcademicOS settings export.");
      return;
    }
    const names = Object.keys(sections).join(", ");
    const confirmed = window.confirm(
      `Import settings from "${file.name}"? This replaces the current values of these sections: ${names}.`,
    );
    if (!confirmed) {
      setMessage("Import cancelled.");
      return;
    }
    setBusy("import");
    try {
      const doc = await importSettings(sections);
      onImported(doc);
      setMessage(`Imported ${Object.keys(sections).length} section(s): ${names}.`);
    } catch (err) {
      setError(toErrorMessage(err, "Could not import the settings file."));
    } finally {
      setBusy(null);
    }
  };

  const handleReset = async () => {
    if (busy) return;
    clear();
    const confirmed = window.confirm(
      "Reset ALL preferences to factory defaults? This clears every settings value (the profile photo is kept). This cannot be undone.",
    );
    if (!confirmed) {
      setMessage("Reset cancelled.");
      return;
    }
    setBusy("reset");
    try {
      const doc = await resetSettings();
      onImported(doc);
      setMessage("All preferences were reset to factory defaults.");
    } catch (err) {
      setError(toErrorMessage(err, "Could not reset the preferences."));
    } finally {
      setBusy(null);
    }
  };

  return (
    <SectionCard
      title="Backup & restore"
      description="Move your preferences between machines or start over. The export contains settings only — it is not a backup of your AcademicOS data."
    >
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          aria-label="Export settings"
          className={GHOST_BUTTON_CLASS}
          disabled={busy !== null}
          onClick={() => void handleExport()}
        >
          {busy === "export" ? "Exporting…" : "Export settings"}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          aria-label="Import settings file"
          accept="application/json,.json"
          className="hidden"
          onChange={(event) => {
            void handleImportFile(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
        <button
          type="button"
          aria-label="Import settings"
          className={GHOST_BUTTON_CLASS}
          disabled={busy !== null}
          onClick={() => fileInputRef.current?.click()}
        >
          {busy === "import" ? "Importing…" : "Import settings"}
        </button>
        <button
          type="button"
          aria-label="Reset preferences"
          className={DANGER_BUTTON_CLASS}
          disabled={busy !== null}
          onClick={() => void handleReset()}
        >
          {busy === "reset" ? "Resetting…" : "Reset to defaults"}
        </button>
      </div>
      <p className="text-xs text-[var(--text-tertiary)]">
        Import expects a file produced by “Export settings” (a JSON document with a sections map).
        Reset restores factory defaults for every section.
      </p>
      <span
        role="status"
        aria-live="polite"
        aria-label="Backup status"
        className="block text-sm text-[var(--success)]"
      >
        {message ?? ""}
      </span>
      {error ? (
        <span role="alert" className="block text-sm text-[var(--danger)]">
          {error}
        </span>
      ) : null}
    </SectionCard>
  );
}

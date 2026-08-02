"use client";

import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { updateMeeting } from "@/lib/api/committees";
import { Spinner } from "@/components/features/objects/Spinner";
import type { MeetingResponse } from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

/**
 * Minutes + key decisions (PART 3). Decisions are a plain list — one per line
 * in the editor; the backend rejects empty entries (422).
 */
export function MinutesDecisionsPanel({
  meeting,
  onSaved,
  onError,
}: {
  meeting: MeetingResponse;
  onSaved: (meeting: MeetingResponse) => void;
  onError: (message: string) => void;
}) {
  const [minutes, setMinutes] = useState(meeting.minutes ?? "");
  const [decisionsText, setDecisionsText] = useState((meeting.decisions ?? []).join("\n"));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setMinutes(meeting.minutes ?? "");
    setDecisionsText((meeting.decisions ?? []).join("\n"));
  }, [meeting.minutes, meeting.decisions]);

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const decisions = decisionsText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      const updated = await updateMeeting(meeting.id, {
        minutes: minutes.trim() || null,
        decisions,
        uploaded_by: meeting.uploaded_by || "faculty:ui",
      });
      onSaved(updated);
    } catch (err) {
      onError(toErrorMessage(err, "Could not save the minutes."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section
      aria-label="Minutes and decisions"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Minutes & Decisions</h2>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-60"
        >
          {saving ? <Spinner className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" aria-hidden="true" />}
          {saving ? "Saving…" : "Save minutes"}
        </button>
      </div>
      <div className="space-y-3">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
            Minutes
          </span>
          <textarea
            value={minutes}
            onChange={(event) => setMinutes(event.target.value)}
            rows={4}
            aria-label="Meeting minutes"
            placeholder="Summary of the proceedings…"
            className={FIELD_CLASS}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
            Key decisions (one per line)
          </span>
          <textarea
            value={decisionsText}
            onChange={(event) => setDecisionsText(event.target.value)}
            rows={3}
            aria-label="Key decisions"
            placeholder={"Approved the L1 vendor quote\nRatified the revised budget head"}
            className={FIELD_CLASS}
          />
        </label>
      </div>
    </section>
  );
}

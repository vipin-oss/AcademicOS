"use client";

import { Award } from "lucide-react";
import { ParticipationRoleBadge } from "@/components/features/events/EventBadges";
import type { EventResponse } from "@/types";

/**
 * Certificates lens: every participation row carrying a certificate document
 * (PART 2) plus the PART 5 "certificates issued" counter. Read-only — the
 * documents themselves live in the Documents module / documents lens.
 */
export function CertificatesPanel({ event }: { event: EventResponse }) {
  const rows = event.participation.filter((row) => row.certificate);
  const issued = event.registration?.certificates_issued ?? 0;
  return (
    <section
      aria-label="Certificates"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">
        Certificates ({rows.length})
      </h2>
      {rows.length === 0 ? (
        <p className="mt-3 text-sm text-[var(--text-tertiary)]">
          No certificates yet — link one in the My Participation panel.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {rows.map((row, index) => (
            <li
              key={index}
              className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm"
            >
              <Award className="h-4 w-4 text-[var(--success)]" aria-hidden="true" />
              {row.role ? <ParticipationRoleBadge role={row.role} /> : null}
              <span className="text-[var(--text-primary)]">{row.certificate?.title}</span>
              {row.remarks ? (
                <span className="text-xs text-[var(--text-tertiary)]">· {row.remarks}</span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-[var(--text-tertiary)]">
        Certificates issued to participants at this event: {issued}
      </p>
    </section>
  );
}

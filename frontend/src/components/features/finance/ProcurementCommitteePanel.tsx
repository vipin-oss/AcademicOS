"use client";

import Link from "next/link";
import { Users } from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { ProposalResponse } from "@/types";

/**
 * PART 2 procurement committee lens: the linked purchase committees (reused
 * from the Committees module), the approval meeting pointer (resolved
 * server-side) and the minutes / recommendations recorded for this proposal.
 */
export function ProcurementCommitteePanel({ proposal }: { proposal: ProposalResponse }) {
  const committees = proposal.links?.committees ?? [];
  const meeting = proposal.approval_meeting ?? null;
  const empty =
    committees.length === 0 &&
    !meeting &&
    !proposal.minutes &&
    !proposal.recommendations;

  return (
    <section
      aria-label="Procurement committee"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">Procurement Committee</h2>
      {empty ? (
        <p className="mt-3 text-sm text-[var(--text-tertiary)]">
          No purchase committee linked yet — edit the proposal to link the committee, its
          approval meeting and the minutes.
        </p>
      ) : (
        <div className="mt-3 space-y-4 text-sm">
          {committees.length > 0 ? (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                Purchase committees
              </p>
              <ul className="mt-1.5 space-y-1">
                {committees.map((committee) => (
                  <li key={committee.id} className="flex items-center gap-2">
                    <Users
                      className="h-3.5 w-3.5 text-[var(--text-tertiary)]"
                      aria-hidden="true"
                    />
                    <Link
                      href={`/committees/${encodeURIComponent(committee.id)}`}
                      className="text-[var(--accent)] hover:underline"
                    >
                      {committee.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {meeting ? (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                Approval meeting
              </p>
              <p className="mt-1.5">
                <Link
                  href={`/committees/meetings/${encodeURIComponent(meeting.id)}`}
                  className="text-[var(--accent)] hover:underline"
                >
                  {meeting.title}
                </Link>
              </p>
              <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                {[
                  meeting.meeting_number ? `No. ${meeting.meeting_number}` : null,
                  meeting.meeting_date ? formatDate(meeting.meeting_date) : null,
                  meeting.mode,
                  meeting.venue,
                ]
                  .filter(Boolean)
                  .join(" · ") || "—"}
              </p>
            </div>
          ) : null}

          {proposal.minutes ? (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                Minutes
              </p>
              <p className="mt-1.5 whitespace-pre-wrap text-[var(--text-secondary)]">
                {proposal.minutes}
              </p>
            </div>
          ) : null}

          {proposal.recommendations ? (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                Recommendations
              </p>
              <p className="mt-1.5 whitespace-pre-wrap text-[var(--text-secondary)]">
                {proposal.recommendations}
              </p>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

"use client";

import Link from "next/link";
import { UserRound } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { MemberRoleBadge } from "./CommitteeBadges";
import type { CommitteeMember } from "@/types";

/**
 * PART 2 members panel. The list is resolved server-side (leadership first,
 * then name); management happens through the committee modal (whole-list
 * replace), which keeps the faculty-side backlinks consistent.
 */
export function MembersPanel({
  members,
  onManage,
}: {
  members: CommitteeMember[];
  onManage?: () => void;
}) {
  return (
    <section
      aria-label="Committee members"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Members ({members.length})
        </h2>
        {onManage ? (
          <button
            type="button"
            onClick={onManage}
            className="rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            Manage members
          </button>
        ) : null}
      </div>
      {members.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No members yet — manage members to add the chairperson, convener and members.
        </p>
      ) : (
        <ul className="divide-y divide-[var(--border-subtle)]">
          {members.map((member) => (
            <li key={`${member.id}-${member.role}`} className="flex items-start gap-3 py-2.5">
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--bg-hover)] text-[var(--text-tertiary)]">
                <UserRound className="h-4 w-4" aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    href={
                      member.object_type === "faculty"
                        ? `/faculty/${encodeURIComponent(member.id)}`
                        : member.object_type === "student"
                          ? `/students/${encodeURIComponent(member.id)}`
                          : `/objects/${encodeURIComponent(member.id)}`
                    }
                    className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                  >
                    {member.name}
                  </Link>
                  <MemberRoleBadge role={member.role} />
                </div>
                <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                  {[
                    member.start_date
                      ? `${formatDate(member.start_date)} → ${formatDate(member.end_date)}`
                      : null,
                    member.remarks,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

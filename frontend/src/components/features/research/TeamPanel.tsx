"use client";

import Link from "next/link";
import { PROJECT_TEAM_GROUPS } from "@/lib/research/constants";
import type { ProjectResponse } from "@/types";

/** PART 4 team panel: PI / Co-PI(s) / Research Team (typed person edges). */
export function TeamPanel({ project }: { project: ProjectResponse }) {
  const empty = PROJECT_TEAM_GROUPS.every(
    (group) => (project.team?.[group.value] ?? []).length === 0,
  );
  return (
    <section
      aria-label="Project team"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">Team</h2>
      {empty ? (
        <p className="mt-2 text-sm text-[var(--text-tertiary)]">
          No team linked yet — edit the project to add the PI, Co-PIs and research team.
        </p>
      ) : (
        <dl className="mt-2 space-y-3">
          {PROJECT_TEAM_GROUPS.map((group) => {
            const members = project.team?.[group.value] ?? [];
            if (members.length === 0) return null;
            return (
              <div key={group.value}>
                <dt className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                  {group.label}
                </dt>
                <dd className="mt-1 flex flex-wrap gap-1.5">
                  {members.map((member) => (
                    <Link
                      key={member.id}
                      href={`/objects/${encodeURIComponent(member.id)}`}
                      className="inline-flex items-center gap-1 rounded-full border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
                    >
                      {member.title}
                      <span className="text-[var(--text-tertiary)]">
                        ({member.object_type})
                      </span>
                    </Link>
                  ))}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
    </section>
  );
}

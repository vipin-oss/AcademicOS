"use client";

import { LifecycleStatusBadge, PriorityBadge, ResearchStatusBadge } from "./ResearchBadges";
import { formatDate } from "@/lib/research/constants";
import type { ProjectResponse } from "@/types";

/** Compact project identity header for the workspace page (with action slot). */
export function ProjectHeader({
  project,
  actions,
}: {
  project: ProjectResponse;
  actions?: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">{project.title}</h2>
            <LifecycleStatusBadge status={project.lifecycle_status} />
            {project.priority ? <PriorityBadge priority={project.priority} /> : null}
            <ResearchStatusBadge status={project.status} />
          </div>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {[
              project.project_code,
              project.department,
              project.grant_number ? `Grant no. ${project.grant_number}` : null,
            ]
              .filter(Boolean)
              .join(" · ") || " "}
          </p>
          <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
            {[
              project.start_date ? `${formatDate(project.start_date)} → ${formatDate(project.end_date)}` : null,
              project.duration,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          {project.tags.length > 0 ? (
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">
              {project.tags.map((tag) => `#${tag}`).join(" ")}
            </p>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {project.objectives ? (
        <p className="mt-3 border-t border-[var(--border-subtle)] pt-3 text-sm text-[var(--text-secondary)]">
          <span className="font-medium text-[var(--text-primary)]">Objectives: </span>
          {project.objectives}
        </p>
      ) : null}
    </div>
  );
}

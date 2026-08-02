"use client";

import Link from "next/link";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { formatAmount, formatDate } from "@/lib/research/constants";
import { LifecycleStatusBadge, PriorityBadge } from "./ResearchBadges";
import type { ProjectResponse } from "@/types";

function AgencyLine({ project }: { project: ProjectResponse }) {
  const agencies = project.links?.agencies ?? [];
  if (agencies.length === 0) return null;
  return (
    <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
      {agencies.map((agency) => agency.title).join(", ")}
    </p>
  );
}

/** The projects registry table (mirrors StudentTable structure). */
export function ProjectTable({
  projects,
  loading = false,
}: {
  projects: ProjectResponse[];
  loading?: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[860px] border-collapse text-left" aria-busy={loading}>
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th scope="col" className="px-4 py-3 font-medium">Project</th>
            <th scope="col" className="px-4 py-3 font-medium">Department</th>
            <th scope="col" className="px-4 py-3 font-medium">Lifecycle</th>
            <th scope="col" className="px-4 py-3 font-medium">Duration</th>
            <th scope="col" className="px-4 py-3 font-medium">Budget</th>
            <th scope="col" className="px-4 py-3 font-medium">Priority</th>
          </tr>
        </thead>
        <tbody>
          {/* TableSkeleton emits bare <tr>s — valid only inside <tbody>. */}
          {loading ? (
            <TableSkeleton rows={6} cols={6} />
          ) : (
            projects.map((project) => (
              <tr
                key={project.id}
                className="border-b border-[var(--border-subtle)] align-top transition-colors last:border-0 hover:bg-[var(--bg-hover)]"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/research/projects/${encodeURIComponent(project.id)}`}
                    className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                  >
                    {project.title}
                  </Link>
                  <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                    {project.project_code ?? "No code"}
                  </p>
                  <AgencyLine project={project} />
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {project.department ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <LifecycleStatusBadge status={project.lifecycle_status} />
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {formatDate(project.start_date)}
                  {project.end_date ? ` → ${formatDate(project.end_date)}` : ""}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {formatAmount(project.budget_approved)}
                </td>
                <td className="px-4 py-3">
                  {project.priority ? <PriorityBadge priority={project.priority} /> : "—"}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

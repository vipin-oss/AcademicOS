import Link from "next/link";
import { Badge } from "@/components/features/documents/DocumentBadge";
import { roleLabel } from "./FacultyBadges";
import type { FacultyResponse } from "@/types";

/**
 * PART 3 research integration: the projects this faculty leads/co-leads/works
 * in and the grants funding those projects (derived lens — links into the
 * Research module workspaces).
 */
export function ResearchPanel({ faculty }: { faculty: FacultyResponse }) {
  const projects = faculty.research?.projects ?? [];
  const grants = faculty.research?.grants ?? [];
  const empty = projects.length === 0 && grants.length === 0;
  return (
    <section
      aria-label="Research profile"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">Research</h2>
      {empty ? (
        <p className="mt-2 text-sm text-[var(--text-tertiary)]">
          No projects or grants yet — link this faculty as PI / Co-PI / team member from the
          Research module.
        </p>
      ) : (
        <dl className="mt-2 space-y-3">
          {projects.length > 0 ? (
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                Projects
              </dt>
              <dd className="mt-1">
                <ul className="space-y-1.5">
                  {projects.map((project) => (
                    <li key={`${project.id}-${project.kind}`} className="flex flex-wrap items-center gap-2 text-sm">
                      <Link
                        href={`/research/projects/${encodeURIComponent(project.id)}`}
                        className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                      >
                        {project.title}
                      </Link>
                      <Badge className="bg-[var(--accent-subtle)] text-[var(--accent)]">
                        {roleLabel(project.kind)}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
          ) : null}
          {grants.length > 0 ? (
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                Grants
              </dt>
              <dd className="mt-1">
                <ul className="space-y-1.5">
                  {grants.map((grant) => (
                    <li key={grant.id} className="text-sm">
                      <Link
                        href={`/research/grants/${encodeURIComponent(grant.id)}`}
                        className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                      >
                        {grant.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
          ) : null}
        </dl>
      )}
    </section>
  );
}

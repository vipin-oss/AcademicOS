"use client";

import Link from "next/link";
import { COMMITTEE_LINK_GROUPS } from "@/lib/committees/constants";
import type { CommitteeLinkedObject, CommitteeLinkGroup } from "@/types";

/** Group-aware destination routes (the linked modules' detail pages). */
function linkHref(group: CommitteeLinkGroup, id: string): string {
  const encoded = encodeURIComponent(id);
  switch (group) {
    case "projects":
      return `/research/projects/${encoded}`;
    case "grants":
      return `/research/grants/${encoded}`;
    case "students":
      return `/students/${encoded}`;
    case "publications":
      return `/publications/${encoded}`;
    default:
      return `/objects/${encoded}`;
  }
}

/**
 * PART 7 research links: the committee's related_to edges grouped by module.
 * Whole-group replace happens in the committee modal (same contract as the
 * research team panels).
 */
export function LinkedLinksPanel({
  links,
}: {
  links: Partial<Record<CommitteeLinkGroup, CommitteeLinkedObject[]>>;
}) {
  const empty = COMMITTEE_LINK_GROUPS.every(
    (group) => (links?.[group.value] ?? []).length === 0,
  );
  return (
    <section
      aria-label="Linked research objects"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">Linked Research & Records</h2>
      {empty ? (
        <p className="mt-2 text-sm text-[var(--text-tertiary)]">
          Nothing linked yet — edit the committee to link projects, grants, students and
          publications.
        </p>
      ) : (
        <dl className="mt-2 space-y-3">
          {COMMITTEE_LINK_GROUPS.map((group) => {
            const items = links?.[group.value] ?? [];
            if (items.length === 0) return null;
            return (
              <div key={group.value}>
                <dt className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                  {group.label}
                </dt>
                <dd className="mt-1 flex flex-wrap gap-1.5">
                  {items.map((item) => (
                    <Link
                      key={item.id}
                      href={linkHref(group.value, item.id)}
                      className="inline-flex items-center gap-1 rounded-full border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
                    >
                      {item.title}
                      <span className="text-[var(--text-tertiary)]">({item.object_type})</span>
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

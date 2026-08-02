"use client";

import Link from "next/link";
import type { ProposalLinkedObject, ProposalLinkGroup } from "@/types";

const GROUPS: { value: ProposalLinkGroup; label: string }[] = [
  { value: "projects", label: "Research Projects" },
  { value: "grants", label: "Grants" },
  { value: "committees", label: "Committees" },
];

/** Group-aware destination routes (the linked modules' detail pages). */
function linkHref(group: ProposalLinkGroup, id: string): string {
  const encoded = encodeURIComponent(id);
  switch (group) {
    case "projects":
      return `/research/projects/${encoded}`;
    case "grants":
      return `/research/grants/${encoded}`;
    case "committees":
      return `/committees/${encoded}`;
    default:
      return `/objects/${encoded}`;
  }
}

/**
 * PART 9/2 links: the proposal's related_to edges grouped by module.
 * Whole-group replace happens in the proposal modal (same contract as the
 * committees module).
 */
export function LinkedLinksPanel({
  links,
}: {
  links: Partial<Record<ProposalLinkGroup, ProposalLinkedObject[]>>;
}) {
  const empty = GROUPS.every((group) => (links?.[group.value] ?? []).length === 0);
  return (
    <section
      aria-label="Linked research & governance objects"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
        Linked Research &amp; Governance
      </h2>
      {empty ? (
        <p className="mt-3 text-sm text-[var(--text-tertiary)]">
          No linked projects, grants or committees yet.
        </p>
      ) : (
        <div className="mt-3 space-y-4">
          {GROUPS.map((group) => {
            const items = links?.[group.value] ?? [];
            if (items.length === 0) return null;
            return (
              <div key={group.value}>
                <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                  {group.label}
                </p>
                <ul className="mt-1.5 space-y-1">
                  {items.map((item) => (
                    <li key={item.id}>
                      <Link
                        href={linkHref(group.value, item.id)}
                        className="text-sm text-[var(--accent)] hover:underline"
                      >
                        {item.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

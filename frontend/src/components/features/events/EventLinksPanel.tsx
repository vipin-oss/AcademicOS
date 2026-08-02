"use client";

import Link from "next/link";
import type { EventLinkedObject, EventLinkGroup } from "@/types";

const GROUPS: { value: Exclude<EventLinkGroup, "faculty" | "students">; label: string }[] = [
  { value: "projects", label: "Research Projects" },
  { value: "grants", label: "Grants" },
  { value: "committees", label: "Committees" },
  { value: "publications", label: "Publications" },
];

/** Group-aware destination routes (the linked modules' detail pages). */
function linkHref(group: string, id: string): string {
  const encoded = encodeURIComponent(id);
  switch (group) {
    case "projects":
      return `/research/projects/${encoded}`;
    case "grants":
      return `/research/grants/${encoded}`;
    case "committees":
      return `/committees/${encoded}`;
    case "publications":
      return `/publications/${encoded}`;
    default:
      return `/objects/${encoded}`;
  }
}

/**
 * PART 7 research/governance lens: the event's related_to edges grouped by
 * module. Whole-group replace happens in the event modal (same contract as
 * the finance module); faculty/students have their own panels.
 */
export function EventLinksPanel({
  links,
}: {
  links: Partial<Record<EventLinkGroup, EventLinkedObject[]>>;
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
          No linked projects, grants, committees or publications yet.
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

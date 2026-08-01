import Link from "next/link";
import { Link2 } from "lucide-react";
import { LINK_GROUPS } from "@/lib/publications/constants";
import type { PublicationResponse } from "@/types";

/**
 * The reference-manager "Linked X" panes: Projects / Grants / Students /
 * Faculty / Departments / Events / Committees. Each entry links into the
 * Objects explorer (the Object is the single source of truth — the
 * publication only carries typed edges to it).
 */
export function PublicationLinks({
  publication,
}: {
  publication: PublicationResponse;
}) {
  const anyLinks = LINK_GROUPS.some(
    ({ value }) => (publication.links?.[value] ?? []).length > 0,
  );

  if (!anyLinks) {
    return (
      <p className="text-sm text-[var(--text-tertiary)]">
        Not linked to any projects, grants, people, or departments yet. Link
        them via Edit to power object-centric lenses (“papers funded by Grant
        X”, “papers with Student Y”).
      </p>
    );
  }

  return (
    <dl className="space-y-3 text-sm">
      {LINK_GROUPS.map(({ value, label }) => {
        const entries = publication.links?.[value] ?? [];
        if (entries.length === 0) return null;
        return (
          <div
            key={value}
            className="flex flex-col gap-1 border-b border-[var(--border-subtle)] py-2 last:border-0 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4"
          >
            <dt className="shrink-0 text-[var(--text-tertiary)]">{label}</dt>
            <dd className="flex flex-wrap justify-start gap-1.5 sm:justify-end">
              {entries.map((entry) => (
                <Link
                  key={entry.id}
                  href={`/objects/${encodeURIComponent(entry.id)}`}
                  title={`${entry.title} (${entry.kind})`}
                  className="inline-flex items-center gap-1 rounded-full bg-[var(--bg-hover)] px-2.5 py-0.5 text-xs text-[var(--accent)] transition-colors hover:bg-[var(--accent-subtle)]"
                >
                  <Link2 className="h-3 w-3" aria-hidden="true" />
                  {entry.title}
                </Link>
              ))}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

"use client";

import Link from "next/link";
import { BookOpen } from "lucide-react";
import { useObjectPublications } from "@/hooks/useObjectPublications";
import { formatAuthorsShort, venueOf } from "@/lib/publications/constants";
import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";

/**
 * "Publications" section shown on the Object detail page — the object lens:
 * papers linked to THIS project / grant / student / department / event. The
 * inverse navigation of the publication's own "Linked Objects" pane.
 *
 * Degrades gracefully (same contract as the Documents section): a failing
 * request renders a muted empty state and never breaks the Object page.
 */
export function ObjectPublications({ objectId }: { objectId: string }) {
  const { publications, loading, error } = useObjectPublications(objectId);

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <CardSkeleton lines={2} />
        <CardSkeleton lines={2} />
      </div>
    );
  }

  if (error || publications.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface-2)] px-6 py-8 text-center">
        <BookOpen className="h-6 w-6 text-[var(--text-tertiary)]" aria-hidden="true" />
        <p className="text-sm font-medium text-[var(--text-primary)]">No publications linked</p>
        <p className="max-w-sm text-xs text-[var(--text-tertiary)]">
          Add a publication from the Publications module and link it to this object
          to see it here.
        </p>
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {publications.map((publication) => (
        <li key={publication.id}>
          <Link
            href={`/publications/${encodeURIComponent(publication.id)}`}
            className="block rounded-lg border border-[var(--border-subtle)] px-3 py-2.5 transition-colors hover:bg-[var(--bg-hover)]"
          >
            <span className="block truncate text-sm font-medium text-[var(--text-primary)]">
              {publication.title}
            </span>
            <span className="mt-0.5 block truncate text-xs text-[var(--text-tertiary)]">
              {formatAuthorsShort(publication.authors)} · {venueOf(publication)}
              {publication.year ? ` · ${publication.year}` : ""}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

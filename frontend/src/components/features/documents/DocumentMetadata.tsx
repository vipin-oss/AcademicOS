import Link from "next/link";
import { Tag } from "lucide-react";
import { titleCase } from "@/lib/utils";
import type { DocumentResponse } from "@/types";

/**
 * Read-only metadata view for a document: the linked object, its description
 * and its tags. Tags render as chips; the linked object is a real link.
 */
export function DocumentMetadata({ document }: { document: DocumentResponse }) {
  const objectHref = document.object_id
    ? `/objects/${encodeURIComponent(document.object_id)}`
    : null;
  const tags = document.tags ?? [];

  if (!document.description && tags.length === 0 && !objectHref) {
    return (
      <p className="rounded-lg border border-dashed border-[var(--border-strong)] px-3 py-4 text-sm text-[var(--text-tertiary)]">
        No metadata yet.
      </p>
    );
  }

  return (
    <dl className="space-y-3 text-sm">
      {objectHref ? (
        <div className="flex flex-col gap-0.5 border-b border-[var(--border-subtle)] py-2 last:border-0 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
          <dt className="shrink-0 text-[var(--text-tertiary)]">Linked object</dt>
          <dd className="break-words text-right">
            <Link
              href={objectHref}
              className="text-[var(--accent)] hover:underline"
              title={document.object_title ?? document.object_id ?? undefined}
            >
              {document.object_title ?? document.object_id ?? "—"}
            </Link>
          </dd>
        </div>
      ) : null}

      {document.description ? (
        <div className="flex flex-col gap-0.5 border-b border-[var(--border-subtle)] py-2 last:border-0 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
          <dt className="shrink-0 text-[var(--text-tertiary)]">Description</dt>
          <dd className="break-words text-[var(--text-primary)] sm:text-right">
            {document.description}
          </dd>
        </div>
      ) : null}

      {tags.length > 0 ? (
        <div className="flex flex-col gap-1 border-b border-[var(--border-subtle)] py-2 last:border-0 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
          <dt className="flex shrink-0 items-center gap-1.5 text-[var(--text-tertiary)]">
            <Tag className="h-3.5 w-3.5" aria-hidden="true" /> Tags
          </dt>
          <dd className="flex flex-wrap justify-start gap-1.5 sm:justify-end">
            {tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-[var(--bg-hover)] px-2 py-0.5 text-xs text-[var(--text-secondary)]"
              >
                {tag}
              </span>
            ))}
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

import type { ReactNode } from "react";
import { BookOpen, CalendarDays, ExternalLink, Upload, Users } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { DOI_URL, formatAuthorsShort } from "@/lib/publications/constants";
import type { PublicationResponse } from "@/types";
import { DocumentVersionBadge } from "@/components/features/documents/DocumentBadge";
import {
  PipelineStageBadge,
  PublicationStatusBadge,
  PublicationTypeBadge,
  QuartileBadge,
} from "./PublicationBadge";

/**
 * Detail-page header: title, authors, badges (type / quartile / pipeline /
 * status / version) and identifiers. Stacks on mobile, actions wrap instead
 * of overflowing. (Mirrors the Documents header.)
 */
export function PublicationHeader({
  publication,
  actions,
}: {
  publication: PublicationResponse;
  actions?: ReactNode;
}) {
  const authors = formatAuthorsShort(publication.authors);

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 flex-1 gap-3">
          <BookOpen
            className="mt-1 h-11 w-11 shrink-0 rounded-lg bg-[var(--accent-subtle)] p-2.5 text-[var(--accent)]"
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <h1 className="break-words text-xl font-semibold text-[var(--text-primary)] sm:text-2xl">
              {publication.title}
            </h1>

            {publication.authors.length > 0 ? (
              <p className="mt-1.5 flex items-center gap-1.5 break-words text-sm text-[var(--text-secondary)]">
                <Users className="h-4 w-4 shrink-0 text-[var(--text-tertiary)]" aria-hidden="true" />
                {authors}
              </p>
            ) : null}

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <PublicationStatusBadge status={publication.status} />
              <PublicationTypeBadge type={publication.publication_type} />
              {publication.quartile ? <QuartileBadge quartile={publication.quartile} /> : null}
              {publication.pipeline_stage ? (
                <PipelineStageBadge stage={publication.pipeline_stage} />
              ) : null}
              <DocumentVersionBadge version={publication.version} />
            </div>

            <dl className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-[var(--text-secondary)]">
              <div className="flex items-center gap-1.5">
                <Upload className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                <dt className="sr-only">Added by</dt>
                <dd className="break-all">{publication.uploaded_by || "—"}</dd>
              </div>
              <div className="flex items-center gap-1.5">
                <CalendarDays className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                <dt className="sr-only">Added at</dt>
                <dd>{formatDate(publication.created_at)}</dd>
              </div>
            </dl>

            <p className="mt-2 break-all font-mono text-xs text-[var(--text-tertiary)]">
              {publication.id}
              {publication.doi ? (
                <>
                  {" · "}
                  <a
                    href={`${DOI_URL}${publication.doi}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[var(--accent)] hover:underline"
                  >
                    doi:{publication.doi}
                    <ExternalLink className="ml-0.5 inline h-3 w-3" aria-hidden="true" />
                  </a>
                </>
              ) : null}
            </p>
          </div>
        </div>

        {actions ? (
          <div className="flex flex-wrap gap-2 lg:justify-end">{actions}</div>
        ) : null}
      </div>
    </div>
  );
}

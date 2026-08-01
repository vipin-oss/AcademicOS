"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { KeyboardEvent } from "react";
import { BookOpen, FileDown } from "lucide-react";
import { titleCase } from "@/lib/utils";
import {
  formatAuthorsShort,
  locatorOf,
  venueOf,
} from "@/lib/publications/constants";
import type { PublicationResponse } from "@/types";
import {
  PipelineStageBadge,
  PublicationStatusBadge,
  PublicationTypeBadge,
  QuartileBadge,
} from "./PublicationBadge";

export function PublicationRow({ publication }: { publication: PublicationResponse }) {
  const router = useRouter();

  // The ONLY place the publication id is encoded — mirrors the Documents row.
  const href = `/publications/${encodeURIComponent(publication.id)}`;

  const onKeyDown = (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      router.push(href);
    }
  };

  return (
    <tr
      role="link"
      tabIndex={0}
      aria-label={`Open ${publication.title}`}
      onClick={() => router.push(href)}
      onKeyDown={onKeyDown}
      className="cursor-pointer border-t border-[var(--border-subtle)] transition-colors hover:bg-[var(--bg-hover)] focus:bg-[var(--bg-hover)] focus:outline-none"
    >
      {/* Publication title + authors */}
      <td className="max-w-[280px] px-4 py-3 sm:max-w-none">
        <div className="flex items-center gap-3">
          <BookOpen
            className="h-9 w-9 shrink-0 rounded-lg bg-[var(--accent-subtle)] p-2 text-[var(--accent)]"
            aria-hidden="true"
          />
          <div className="min-w-0">
            <Link
              href={href}
              onClick={(event) => event.stopPropagation()}
              className="block truncate font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
              title={publication.title}
            >
              {publication.title}
            </Link>
            <span className="mt-0.5 block truncate text-xs text-[var(--text-tertiary)]">
              {formatAuthorsShort(publication.authors)}
              <span className="sm:hidden"> · {publication.year ?? titleCase(publication.publication_type)}</span>
            </span>
          </div>
        </div>
      </td>

      {/* Type */}
      <td className="hidden px-4 py-3 text-[var(--text-secondary)] sm:table-cell">
        <PublicationTypeBadge type={publication.publication_type} />
      </td>

      {/* Venue (journal / conference) + locator */}
      <td className="hidden max-w-[200px] px-4 py-3 text-[var(--text-secondary)] md:table-cell">
        <span className="block truncate" title={venueOf(publication)}>
          {venueOf(publication)}
        </span>
        <span className="mt-0.5 block truncate text-xs text-[var(--text-tertiary)]">
          {locatorOf(publication)}
        </span>
      </td>

      {/* Year */}
      <td className="hidden whitespace-nowrap px-4 py-3 text-[var(--text-secondary)] sm:table-cell">
        {publication.year ?? "—"}
      </td>

      {/* Quartile */}
      <td className="hidden px-4 py-3 lg:table-cell">
        {publication.quartile ? (
          <QuartileBadge quartile={publication.quartile} />
        ) : (
          <span className="text-[var(--text-tertiary)]">—</span>
        )}
      </td>

      {/* Pipeline stage */}
      <td className="hidden px-4 py-3 lg:table-cell">
        {publication.pipeline_stage ? (
          <PipelineStageBadge stage={publication.pipeline_stage} />
        ) : (
          <span className="text-[var(--text-tertiary)]">—</span>
        )}
      </td>

      {/* Status */}
      <td className="px-4 py-3">
        <PublicationStatusBadge status={publication.status} />
      </td>

      {/* Actions */}
      <td className="px-4 py-3 text-right">
        {publication.pdf_url ? (
          <a
            href={publication.pdf_url}
            download={publication.pdf_file_name || publication.title}
            onClick={(event) => event.stopPropagation()}
            aria-label={`Download PDF of ${publication.title}`}
            title="Download PDF"
            className="inline-flex items-center justify-center rounded-lg border border-[var(--border-subtle)] p-1.5 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
          >
            <FileDown className="h-4 w-4" aria-hidden="true" />
          </a>
        ) : (
          <button
            type="button"
            disabled
            aria-label="No PDF attached"
            title="No PDF attached"
            className="inline-flex cursor-not-allowed items-center justify-center rounded-lg border border-[var(--border-subtle)] p-1.5 text-[var(--text-tertiary)] opacity-40"
          >
            <FileDown className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </td>
    </tr>
  );
}

"use client";

import Link from "next/link";
import { Download } from "lucide-react";
import { formatDate, titleCase } from "@/lib/utils";
import type { DocumentResponse } from "@/types";
import {
  DocumentStatusBadge,
  DocumentTypeBadge,
} from "./DocumentBadge";
import { FileIcon } from "./FileIcon";
import { formatFileSize } from "@/lib/documents/constants";

/**
 * Compact document card. Used in the "Documents" section on the Object detail
 * page, where space is tight and a grid reads better than a table.
 */
export function DocumentCard({ document }: { document: DocumentResponse }) {
  const href = `/documents/${encodeURIComponent(document.id)}`;
  const objectHref = document.object_id
    ? `/objects/${encodeURIComponent(document.object_id)}`
    : null;

  return (
    <div className="flex items-center gap-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3 shadow-sm transition-colors hover:border-[var(--border-strong)]">
      <FileIcon type={document.document_type} />
      <div className="min-w-0 flex-1">
        <Link
          href={href}
          className="block truncate font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
          title={document.title}
        >
          {document.title}
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[var(--text-tertiary)]">
          <span className="truncate">{formatFileSize(document.file_size)}</span>
          <span aria-hidden="true">·</span>
          <span className="truncate">{formatDate(document.created_at)}</span>
          {objectHref ? (
            <>
              <span aria-hidden="true">·</span>
              <Link
                href={objectHref}
                className="truncate text-[var(--accent)] hover:underline"
                title={document.object_title ?? document.object_id ?? undefined}
              >
                {document.object_title ?? document.object_id ?? "—"}
              </Link>
            </>
          ) : null}
        </div>
        <div className="mt-2 flex items-center gap-1.5">
          <DocumentTypeBadge type={document.document_type} />
          <DocumentStatusBadge status={document.status} />
        </div>
      </div>
      {document.url ? (
        <a
          href={document.url}
          download={document.file_name || document.title}
          aria-label={`Download ${document.title}`}
          title="Download"
          className="inline-flex shrink-0 items-center justify-center rounded-lg border border-[var(--border-subtle)] p-1.5 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
        >
          <Download className="h-4 w-4" aria-hidden="true" />
        </a>
      ) : null}
    </div>
  );
}

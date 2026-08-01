import type { ReactNode } from "react";
import { CalendarDays, Upload } from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { DocumentResponse } from "@/types";
import {
  DocumentStatusBadge,
  DocumentTypeBadge,
  DocumentVersionBadge,
} from "./DocumentBadge";
import { FileIcon } from "./FileIcon";

/**
 * Detail-page header: title, status / type / version badges and the upload
 * summary. Stacks on mobile, actions wrap instead of overflowing.
 */
export function DocumentHeader({
  document,
  actions,
}: {
  document: DocumentResponse;
  actions?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 flex-1 gap-3">
          <FileIcon type={document.document_type} className="mt-1 h-11 w-11" />
          <div className="min-w-0 flex-1">
            <h1 className="break-words text-xl font-semibold text-[var(--text-primary)] sm:text-2xl">
              {document.title}
            </h1>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <DocumentStatusBadge status={document.status} />
              <DocumentTypeBadge type={document.document_type} />
              <DocumentVersionBadge version={document.version} />
            </div>

            <dl className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-[var(--text-secondary)]">
              <div className="flex items-center gap-1.5">
                <Upload className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                <dt className="sr-only">Uploaded by</dt>
                <dd className="break-all">{document.uploaded_by || "—"}</dd>
              </div>
              <div className="flex items-center gap-1.5">
                <CalendarDays className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                <dt className="sr-only">Uploaded at</dt>
                <dd>{(formatDate(document.created_at))}</dd>
              </div>
            </dl>

            <p className="mt-2 break-all font-mono text-xs text-[var(--text-tertiary)]">
              {document.id}
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

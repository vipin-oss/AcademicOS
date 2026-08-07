"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { KeyboardEvent } from "react";
import { Download } from "lucide-react";
import { formatDate, titleCase } from "@/lib/utils";
import type { DocumentResponse } from "@/types";
import { useDocumentDownload } from "@/hooks/useDocumentDownload";
import { DocumentStatusBadge, DocumentTypeBadge } from "./DocumentBadge";
import { FileIcon } from "./FileIcon";
import { formatFileSize } from "@/lib/documents/constants";

export function DocumentRow({ document }: { document: DocumentResponse }) {
  const router = useRouter();
  const { download, downloadingId, error } = useDocumentDownload();

  // The ONLY place the document id is encoded — mirrors the Objects row.
  const href = `/documents/${encodeURIComponent(document.id)}`;

  const onKeyDown = (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      router.push(href);
    }
  };

  const objectHref = document.object_id
    ? `/objects/${encodeURIComponent(document.object_id)}`
    : null;

  return (
    <tr
      role="link"
      tabIndex={0}
      aria-label={`Open ${document.title}`}
      onClick={() => router.push(href)}
      onKeyDown={onKeyDown}
      className="cursor-pointer border-t border-[var(--border-subtle)] transition-colors hover:bg-[var(--bg-hover)] focus:bg-[var(--bg-hover)] focus:outline-none"
    >
      {/* Document name */}
      <td className="max-w-[240px] px-4 py-3 sm:max-w-none">
        <div className="flex items-center gap-3">
          <FileIcon type={document.document_type} />
          <div className="min-w-0">
            <Link
              href={href}
              onClick={(event) => event.stopPropagation()}
              className="block truncate font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
              title={document.title}
            >
              {document.title}
            </Link>
            <span className="mt-0.5 block truncate text-xs text-[var(--text-tertiary)] sm:hidden">
              {titleCase(document.document_type)} · {document.uploaded_by || "—"}
            </span>
            <span className="mt-0.5 hidden truncate text-xs text-[var(--text-tertiary)] sm:block">
              {document.file_name || "—"} · {formatFileSize(document.file_size)}
            </span>
          </div>
        </div>
      </td>

      {/* Linked object */}
      <td className="hidden max-w-[160px] px-4 py-3 text-[var(--text-secondary)] md:table-cell">
        {objectHref ? (
          <Link
            href={objectHref}
            onClick={(event) => event.stopPropagation()}
            className="block truncate text-[var(--accent)] hover:underline"
            title={document.object_title ?? document.object_id ?? undefined}
          >
            {document.object_title ?? document.object_id ?? "—"}
          </Link>
        ) : (
          <span className="text-[var(--text-tertiary)]">—</span>
        )}
      </td>

      {/* Type */}
      <td className="hidden px-4 py-3 text-[var(--text-secondary)] sm:table-cell">
        <DocumentTypeBadge type={document.document_type} />
      </td>

      {/* Size */}
      <td className="hidden whitespace-nowrap px-4 py-3 text-[var(--text-secondary)] md:table-cell">
        {formatFileSize(document.file_size)}
      </td>

      {/* Uploaded by */}
      <td className="hidden max-w-[160px] truncate px-4 py-3 text-[var(--text-secondary)] md:table-cell">
        {document.uploaded_by || "—"}
      </td>

      {/* Upload date */}
      <td className="hidden whitespace-nowrap px-4 py-3 text-[var(--text-secondary)] lg:table-cell">
        {formatDate(document.created_at)}
      </td>

      {/* Status */}
      <td className="px-4 py-3">
        <DocumentStatusBadge status={document.status} />
      </td>

      {/* Actions */}
      <td className="px-4 py-3 text-right">
        {document.url ? (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              void download(document);
            }}
            disabled={downloadingId === document.id}
            aria-busy={downloadingId === document.id}
            aria-label={
              error
                ? `Download ${document.title} failed: ${error}`
                : `Download ${document.title}`
            }
            title={error ? `Download failed: ${error}` : "Download"}
            className={`inline-flex items-center justify-center rounded-lg border border-[var(--border-subtle)] p-1.5 transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50 ${
              error
                ? "text-[var(--danger)] hover:text-[var(--danger)]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            <Download className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : (
          <button
            type="button"
            disabled
            aria-label="Download unavailable"
            title="Download unavailable"
            className="inline-flex cursor-not-allowed items-center justify-center rounded-lg border border-[var(--border-subtle)] p-1.5 text-[var(--text-tertiary)] opacity-40"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </td>
    </tr>
  );
}

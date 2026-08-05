"use client";

import type { IntakeItem } from "@/types";
import { needsOcr } from "@/lib/intake/extraction";
import { formatBytes } from "@/lib/intake/constants";

const DASH = "—";

function scalar(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return DASH;
  return String(value);
}

function Row({
  label,
  value,
  mono = false,
  title,
}: {
  label: string;
  value: string | number | null | undefined;
  mono?: boolean;
  title?: string;
}) {
  return (
    <div
      aria-label={`Metadata: ${label}: ${scalar(value)}`}
      className="flex flex-col gap-0.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-3 py-2"
    >
      <dt className="text-[11px] font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
        {label}
      </dt>
      <dd
        title={title ?? (typeof value === "string" && value.length > 40 ? value : undefined)}
        className={
          "break-all text-sm text-[var(--text-primary)]" + (mono ? " font-mono text-xs" : "")
        }
      >
        {scalar(value)}
      </dd>
    </div>
  );
}

/**
 * Read-only metadata card for one staged file (M2 Part 2).
 *
 * Every cell renders exactly what the backend recorded: filename/extension/
 * MIME/size/SHA-256 from the M1 stage record; counts, dates, title, author,
 * engine, warnings and embedded metadata from the M2 descriptor. Missing
 * values render as "—" — nothing is fabricated.
 */
export function ExtractionMetadataCard({ item }: { item: IntakeItem }) {
  const ex = item.extraction;
  const embedded = ex?.embedded_metadata ?? {};
  const embeddedKeys = Object.keys(embedded).sort();
  const ocr = needsOcr(item);

  return (
    <div className="flex flex-col gap-3" aria-label="Extraction metadata">
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        <Row label="Filename" value={item.title} />
        <Row label="Extension" value={item.extension ? `.${item.extension}` : DASH} />
        <Row label="MIME" value={item.mime_type} title={item.mime_type ?? undefined} />
        <Row label="Size" value={formatBytes(item.size_bytes)} />
        <Row
          label="SHA-256"
          value={item.sha256 ?? ex?.sha256 ?? null}
          mono
          title={item.sha256 ?? ex?.sha256 ?? undefined}
        />
        <Row label="Page count" value={ex?.page_count ?? null} />
        <Row label="Word count" value={ex?.word_count ?? null} />
        <Row label="Character count" value={ex?.character_count ?? null} />
        <Row label="Title" value={ex?.document_title ?? null} title={ex?.document_title ?? undefined} />
        <Row label="Author" value={ex?.author ?? null} title={ex?.author ?? undefined} />
        <Row label="Creation date" value={ex?.created_at ?? null} mono />
        <Row label="Modification date" value={ex?.modified_at ?? null} mono />
        <Row label="Extraction engine" value={ex?.engine ?? null} />
        <Row label="Extracted at" value={ex?.extracted_at ?? null} mono />
        <Row
          label="Extraction status"
          value={ex ? ex.status : item.error !== null ? "failed" : "pending"}
        />
        <Row label="Needs OCR" value={ocr ? "Yes" : ex?.status === "extracted" ? "No" : DASH} />
        <Row label="Unsupported" value={ex?.status === "unsupported" ? "Yes" : ex ? "No" : DASH} />
        <Row
          label="Text bytes"
          value={ex?.text_bytes ?? null}
        />
      </dl>

      {item.error !== null && (
        <p
          role="alert"
          aria-label="Extraction error"
          className="rounded-lg border border-[var(--danger-subtle)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
        >
          {item.error.stage}: {item.error.message}
        </p>
      )}

      {ex && ex.warnings.length > 0 && (
        <div
          aria-label="Extraction warnings"
          className="rounded-lg border border-[var(--warning-subtle)] bg-[var(--warning-subtle)] px-3 py-2"
        >
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-[var(--warning)]">
            Warnings ({ex.warnings.length})
          </p>
          <ul className="list-inside list-disc text-sm text-[var(--text-secondary)]">
            {ex.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      <div
        aria-label="Embedded metadata"
        className="overflow-hidden rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)]"
      >
        <p className="border-b border-[var(--border-subtle)] px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
          Embedded metadata ({embeddedKeys.length})
        </p>
        {embeddedKeys.length === 0 ? (
          <p className="px-3 py-3 text-sm text-[var(--text-tertiary)]">
            No embedded metadata recorded for this file.
          </p>
        ) : (
          <table className="w-full text-left text-xs" aria-label="Embedded metadata entries">
            <tbody>
              {embeddedKeys.map((key) => (
                <tr key={key} className="border-b border-[var(--border-subtle)] last:border-0">
                  <th
                    scope="row"
                    className="max-w-[12rem] break-all px-3 py-1.5 align-top font-medium text-[var(--text-secondary)]"
                  >
                    {key}
                  </th>
                  <td className="break-all px-3 py-1.5 font-mono text-[var(--text-primary)]">
                    {embedded[key]}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

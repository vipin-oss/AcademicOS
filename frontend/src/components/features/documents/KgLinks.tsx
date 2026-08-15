"use client";

/**
 * Knowledge-graph integration (Sprint M10, final polish).
 *
 * When a document's metadata (or the metadata of the AcademicOS object
 * it is attached to) references other objects (faculty, student,
 * publication, project, event, organization, ...), this panel renders
 * clickable links that open the corresponding object page
 * (`/objects/{id}`). The document's own object is always linked when
 * present.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { Network } from "lucide-react";

import { getObject } from "@/lib/api/objects";
import type { DocumentResponse } from "@/types";

export const KG_OBJECT_PREFIX = "obj:";

const OBJECT_TYPE_LABELS: Record<string, string> = {
  faculty: "Faculty",
  student: "Student",
  publication: "Publication",
  project: "Project",
  event: "Event",
  organization: "Organization",
  course: "Course",
};

/** Extract object references from a metadata record. */
export function extractObjectReferences(
  metadata: Record<string, unknown>,
): { label: string; objectId: string }[] {
  const refs: { label: string; objectId: string }[] = [];
  const candidates: string[] = [];
  for (const [key, value] of Object.entries(metadata)) {
    if (!/faculty|student|publication|project|event|organization|author|related/i.test(key)) {
      continue;
    }
    if (typeof value === "string") candidates.push(value);
    else if (Array.isArray(value)) {
      candidates.push(...value.filter((v): v is string => typeof v === "string"));
    }
  }
  for (const candidate of candidates) {
    const trimmed = candidate.trim();
    if (!trimmed.startsWith(KG_OBJECT_PREFIX)) continue;
    const type = trimmed.split(":")[1] ?? "";
    const label = OBJECT_TYPE_LABELS[type] ?? type;
    refs.push({ label, objectId: trimmed });
  }
  return refs;
}

export function KgLinks({ document }: { document: DocumentResponse }) {
  const [linkedRefs, setLinkedRefs] = useState<{ label: string; objectId: string }[]>([]);

  useEffect(() => {
    let cancelled = false;
    const docMeta = (document as unknown as { metadata?: Record<string, unknown> }).metadata;
    const direct = extractObjectReferences(docMeta ?? {});
    setLinkedRefs(direct);
    // Also pull the metadata of the AcademicOS object this document is
    // attached to (committed intake documents carry it).
    if (document.object_id) {
      getObject(document.object_id)
        .then((obj) => {
          if (cancelled) return;
          const meta = (obj as unknown as { metadata?: Record<string, unknown> }).metadata;
          const refs = extractObjectReferences(meta ?? {});
          setLinkedRefs((prev) => {
            const seen = new Set(prev.map((r) => r.objectId));
            return [...prev, ...refs.filter((r) => !seen.has(r.objectId))];
          });
        })
        .catch(() => {
          /* object not readable — links are best-effort */
        });
    }
    return () => {
      cancelled = true;
    };
  }, [document]);

  const refs = linkedRefs;
  const ownObject = document.object_id ? [
    { label: "Document object", objectId: document.object_id },
  ] : [];

  if (refs.length === 0 && ownObject.length === 0) return null;

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
        <Network className="h-4 w-4 text-[var(--accent)]" /> Related objects
      </h3>
      <ul className="flex flex-wrap gap-2">
        {ownObject.map((ref) => (
          <li key={ref.objectId}>
            <Link
              href={`/objects/${encodeURIComponent(ref.objectId)}`}
              className="inline-flex items-center gap-1 rounded-lg bg-[var(--bg-hover)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-active)] hover:text-[var(--text-primary)]"
            >
              {ref.label}
            </Link>
          </li>
        ))}
        {refs.map((ref) => (
          <li key={ref.objectId}>
            <Link
              href={`/objects/${encodeURIComponent(ref.objectId)}`}
              className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--accent)] hover:bg-[var(--accent)] hover:text-white"
            >
              {ref.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

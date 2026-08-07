"use client";

/**
 * Knowledge-graph integration (Sprint M10).
 *
 * When a document's metadata references AcademicOS objects (faculty,
 * student, publication, project, event, organization, …), this panel
 * renders clickable links that open the corresponding object page
 * (`/objects/{id}`). The metadata keys follow the module conventions
 * (e.g. `related.faculty`, `related.project`, `doc.author`) and may
 * carry either an object id (`obj:faculty:…`) or a plain title.
 */
import Link from "next/link";
import { Network } from "lucide-react";

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

/** Extract object references from document metadata. */
export function extractObjectReferences(
  document: DocumentResponse,
): { label: string; objectId: string }[] {
  const refs: { label: string; objectId: string }[] = [];
  const meta = (document as unknown as { metadata?: Record<string, unknown> }).metadata ?? {};
  const candidates: string[] = [];
  for (const [key, value] of Object.entries(meta)) {
    if (!/faculty|student|publication|project|event|organization|author|related/i.test(key)) {
      continue;
    }
    if (typeof value === "string") candidates.push(value);
    else if (Array.isArray(value)) candidates.push(...value.filter((v): v is string => typeof v === "string"));
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
  const refs = extractObjectReferences(document);
  if (refs.length === 0) return null;

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
        <Network className="h-4 w-4 text-[var(--accent)]" /> Related objects
      </h3>
      <ul className="flex flex-wrap gap-2">
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

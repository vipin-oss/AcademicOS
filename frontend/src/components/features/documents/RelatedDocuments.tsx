/**
 * RelatedDocuments — shows confirmed document relationships.
 *
 * Displays documents that have been linked to the current document.
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import { Link2, Loader2 } from "lucide-react";
import Link from "next/link";
import { fetchRelatedDocuments } from "@/lib/api/entityMatches";

interface RelatedDoc {
  document_id: string;
  title: string;
  object_type: string;
  relationship_kind: string;
}

interface RelatedDocumentsProps {
  documentId: string;
}

export function RelatedDocuments({ documentId }: RelatedDocumentsProps) {
  const [related, setRelated] = useState<RelatedDoc[]>([]);
  const [loading, setLoading] = useState(true);

  const loadRelated = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchRelatedDocuments(documentId);
      setRelated(data.related);
    } catch {
      setRelated([]);
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    loadRelated();
  }, [loadRelated]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading related documents…
      </div>
    );
  }

  if (related.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
      <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
        Related Documents
      </h3>
      <ul className="space-y-2">
        {related.map((doc) => (
          <li key={doc.document_id}>
            <Link
              href={`/documents/${encodeURIComponent(doc.document_id)}`}
              className="inline-flex items-center gap-1.5 text-sm text-[var(--accent)] hover:underline"
            >
              <Link2 className="h-3.5 w-3.5" />
              {doc.title || doc.document_id}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

"use client";

import { FileText } from "lucide-react";
import { useObjectDocuments } from "@/hooks/useObjectDocuments";
import { DocumentCard } from "./DocumentCard";
import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";

/**
 * "Documents" section shown on the Object detail page. Fetches the documents
 * linked to the current object and renders them as cards.
 *
 * Degrades gracefully: if the backend has no documents endpoint yet, the
 * request fails quietly and we show a muted empty state — the (working)
 * Object detail page is never broken by this section.
 */
export function ObjectDocuments({ objectId }: { objectId: string }) {
  const { documents, loading, error } = useObjectDocuments(objectId);

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <CardSkeleton lines={2} />
        <CardSkeleton lines={2} />
      </div>
    );
  }

  if (error || documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface-2)] px-6 py-8 text-center">
        <FileText className="h-6 w-6 text-[var(--text-tertiary)]" aria-hidden="true" />
        <p className="text-sm font-medium text-[var(--text-primary)]">No documents linked</p>
        <p className="max-w-sm text-xs text-[var(--text-tertiary)]">
          Upload a document from the Documents module and link it to this object to see it here.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {documents.map((document) => (
        <DocumentCard key={document.id} document={document} />
      ))}
    </div>
  );
}

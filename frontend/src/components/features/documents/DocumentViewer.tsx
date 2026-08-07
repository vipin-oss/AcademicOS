"use client";

/**
 * Document viewer (Sprint M10) — side-by-side workspace:
 *
 *   left  — native PDF viewer (pdf.js): navigation, zoom, fit modes,
 *           highlight/note/bookmark overlays;
 *   right — extracted text panel: text synchronization (select text ->
 *           approximate PDF region highlight), page notes, annotation list.
 *
 * Non-PDF documents keep the existing DocumentPreview (M3 behaviour).
 */
import { useCallback, useEffect, useState } from "react";
import { Columns2, PanelRightClose, PanelRightOpen } from "lucide-react";

import { listAnnotations } from "@/lib/api/annotations";
import { toErrorMessage } from "@/lib/api/client";
import type { PdfPageText } from "@/lib/pdf/textSync";
import type { DocumentAnnotation, DocumentResponse } from "@/types";
import { DocumentPreview } from "./DocumentPreview";
import { ExtractedTextPanel } from "./ExtractedTextPanel";
import { ImageViewer } from "./ImageViewer";
import { OfficePreview } from "./OfficePreview";
import { PdfViewer } from "./PdfViewer";

export function DocumentViewer({ document }: { document: DocumentResponse }) {
  const [annotations, setAnnotations] = useState<DocumentAnnotation[]>([]);
  const [pagesText, setPagesText] = useState<PdfPageText[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [showText, setShowText] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshAnnotations = useCallback(() => {
    listAnnotations(document.id)
      .then((res) => setAnnotations(res.items))
      .catch((err) => setError(toErrorMessage(err)));
  }, [document.id]);

  useEffect(() => {
    refreshAnnotations();
  }, [refreshAnnotations]);

  if (document.document_type === "png" || document.document_type === "jpg" ||
      document.document_type === "jpeg" || document.document_type === "tiff" ||
      document.document_type === "svg" || document.document_type === "image") {
    return <ImageViewer documentId={document.id} fileName={document.file_name || document.title} />;
  }
  if (document.document_type === "docx" || document.document_type === "pptx" ||
      document.document_type === "xlsx") {
    return <OfficePreview document={document} />;
  }
  if (document.document_type !== "pdf") {
    return <DocumentPreview document={document} />;
  }

  const toggleBookmark = (page: number) => {
    const existing = annotations.find(
      (a) => a.annotation_type === "bookmark" && a.page === page,
    );
    if (existing) {
      void import("@/lib/api/annotations")
        .then((m) => m.deleteAnnotation(existing.annotation_id))
        .then(refreshAnnotations)
        .catch((err) => setError(toErrorMessage(err)));
    } else {
      void import("@/lib/api/annotations")
        .then((m) =>
          m.createAnnotation(document.id, "bookmark", page, { label: "page mark" }),
        )
        .then(refreshAnnotations)
        .catch((err) => setError(toErrorMessage(err)));
    }
  };

  return (
    <div className="space-y-2">
      {error && (
        <p role="alert" className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
          {error}
        </p>
      )}
      <div className="flex gap-3">
        <div className="min-w-0 flex-1">
          <PdfViewer
            documentId={document.id}
            fileName={document.file_name || document.title}
            annotations={annotations}
            onTextReady={setPagesText}
            onToggleBookmark={toggleBookmark}
          />
        </div>
        {showText && (
          <div className="w-[26rem] max-w-[40vw] shrink-0">
            <ExtractedTextPanel
              documentId={document.id}
              annotations={annotations}
              pagesText={pagesText}
              currentPage={currentPage}
              onJump={setCurrentPage}
              onChanged={refreshAnnotations}
              onError={setError}
            />
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={() => setShowText((v) => !v)}
        className="flex items-center gap-1.5 rounded-md border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
      >
        {showText ? (
          <>
            <PanelRightClose className="h-3.5 w-3.5" /> Hide extracted text
          </>
        ) : (
          <>
            <Columns2 className="h-3.5 w-3.5" /> Side-by-side
          </>
        )}
      </button>
    </div>
  );
}

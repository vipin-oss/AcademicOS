"use client";

/**
 * Native PDF viewer (Sprint M10).
 *
 * Renders the original PDF inside AcademicOS with pdf.js (no browser
 * download required): page navigation (previous/next, jump-to-page),
 * zoom (in/out, fit width, fit page) and an annotation overlay —
 * highlights (rects in PDF units, scaled to the current zoom), note
 * markers and bookmark badges, all driven by the persisted annotations
 * from the backend.
 *
 * The pdf.js module is imported lazily inside an effect so the production
 * build stays SSR-safe; the worker is served from /public.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bookmark,
  ChevronLeft,
  ChevronRight,
  Maximize,
  Minus,
  Plus,
  Scissors,
  StickyNote,
} from "lucide-react";

import type { PDFDocumentProxy } from "pdfjs-dist";

import { api, toErrorMessage } from "@/lib/api/client";
import type { PdfSearchMatch } from "@/lib/pdf/searchPdf";
import type { PdfPageText } from "@/lib/pdf/textSync";
import type { DocumentAnnotation } from "@/types";
import { cn } from "@/lib/utils";
import { PdfSearchPanel } from "./PdfSearchPanel";

const MIN_SCALE = 0.25;
const MAX_SCALE = 5.0;
const ZOOM_STEP = 1.25;

export interface PdfViewerProps {
  documentId: string;
  fileName: string;
  annotations: DocumentAnnotation[];
  /** Called once the pdf.js text layer per page is available (text sync). */
  onTextReady: (pages: PdfPageText[]) => void;
  onToggleBookmark: (page: number) => void;
  /** The pdf.js text layer (for Ctrl+F search). */
  pagesText?: PdfPageText[];
  /** The loaded pdf.js document (for thumbnail navigation). */
  onPdfReady?: (pdf: import("pdfjs-dist").PDFDocumentProxy) => void;
  /** Controlled viewer state (multi-document workspace): when provided
   * the viewer reflects these values and reports changes through the
   * callbacks, so tabs preserve page/zoom/fit across switches. */
  page?: number;
  scale?: number;
  fitMode?: "width" | "page" | "custom";
  onPageChange?: (page: number) => void;
  onScaleChange?: (scale: number) => void;
  onFitModeChange?: (fitMode: "width" | "page" | "custom") => void;
}

export function PdfViewer({
  documentId,
  fileName,
  annotations,
  onTextReady,
  onToggleBookmark,
  pagesText = [],
  onPdfReady,
  page,
  scale,
  fitMode,
  onPageChange,
  onScaleChange,
  onFitModeChange,
}: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [internalPage, setInternalPage] = useState(1);
  const [internalScale, setInternalScale] = useState(1);
  const [internalFit, setInternalFit] = useState<"width" | "page" | "custom">("width");
  const [searchMatch, setSearchMatch] = useState<PdfSearchMatch | null>(null);
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);

  const currentPage = page ?? internalPage;
  const currentScale = scale ?? internalScale;
  const currentFit = fitMode ?? internalFit;

  const changePage = useCallback((next: number) => {
    setInternalPage(next);
    onPageChange?.(next);
  }, [onPageChange]);
  const changeScale = useCallback((next: number) => {
    setInternalScale(next);
    onScaleChange?.(next);
  }, [onScaleChange]);
  const changeFit = useCallback((next: "width" | "page" | "custom") => {
    setInternalFit(next);
    onFitModeChange?.(next);
  }, [onFitModeChange]);

  const scaleRef = useRef<number>(1);
  scaleRef.current = currentScale;
  const fitModeRef = useRef<typeof currentFit>("width");
  fitModeRef.current = currentFit;
  const pdfRef = useRef<PDFDocumentProxy | null>(null);

  // Free the pdf.js document on unmount (memory cleanup).
  useEffect(() => {
    return () => {
      const doc = pdfRef.current;
      pdfRef.current = null;
      if (doc) void doc.destroy().catch(() => undefined);
    };
  }, []);

  // Load the document once.
  useEffect(() => {
    let cancelled = false;
    setError(null);
    (async () => {
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        const blob = await api.getBlob(`/documents/${documentId}/download`);
        if (cancelled) return;
        const doc = await pdfjs.getDocument({ data: await blob.arrayBuffer() }).promise;
        if (cancelled) {
          void doc.destroy();
          return;
        }
        setPdfDoc(doc);
        pdfRef.current = doc;
        setPageCount(doc.numPages);
        onPdfReady?.(doc);
        changePage(1);
        // Build the per-page text layer for the side-by-side sync.
        const pages: PdfPageText[] = [];
        for (let n = 1; n <= doc.numPages; n += 1) {
          const textContent = await doc.getPage(n).then((p) => p.getTextContent());
          pages.push({
            page: n,
            items: textContent.items
              .filter((it) => typeof (it as { str?: unknown }).str === "string")
              .map((it) => {
                const textItem = it as { str: string; transform: number[]; width: number; height: number };
                return {
                  str: textItem.str,
                  transform: textItem.transform,
                  width: textItem.width,
                  height: textItem.height,
                };
              }),
          });
        }
        if (!cancelled) onTextReady(pages);
      } catch (err) {
        if (!cancelled) setError(toErrorMessage(err, "The PDF could not be loaded."));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentId, onTextReady]);

  // Render the current page.
  useEffect(() => {
    const pdf = pdfDoc;
    const canvas = canvasRef.current;
    if (!pdf || !canvas) return;
    let cancelled = false;
    (async () => {
      const pageObj = await pdf.getPage(currentPage);
      if (cancelled) return;
      const base = pageObj.getViewport({ scale: 1 });
      const container = containerRef.current;
      let effective = currentScale;
      if (fitModeRef.current === "width" && container) {
        effective = Math.max((container.clientWidth - 24) / base.width, 0.1);
      } else if (fitModeRef.current === "page" && container) {
        effective = Math.max(
          Math.min((container.clientWidth - 24) / base.width, (container.clientHeight - 24) / base.height),
          0.1,
        );
      }
      effective = Math.min(Math.max(effective, MIN_SCALE), MAX_SCALE);
      const viewport = pageObj.getViewport({ scale: effective });
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.floor(viewport.width * ratio);
      canvas.height = Math.floor(viewport.height * ratio);
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      await pageObj.render({ canvasContext: ctx, viewport }).promise;
      changeScale(effective);
    })();
    return () => {
      cancelled = true;
    };
  }, [pdfDoc, currentPage, currentScale, currentFit, changeScale]);

  const goto = useCallback((next: number) => {
    changePage(Math.min(Math.max(next, 1), pageCount || 1));
  }, [changePage, pageCount]);

  const zoom = useCallback((factor: number) => {
    changeFit("custom");
    changeScale(Math.min(Math.max(currentScale * factor, MIN_SCALE), MAX_SCALE));
  }, [changeFit, changeScale, currentScale]);

  const bookmarkFor = annotations.find(
    (a) => a.annotation_type === "bookmark" && a.page === currentPage,
  );
  const highlightRects = annotations
    .filter((a) => a.annotation_type === "highlight" && a.page === currentPage)
    .flatMap((a) => (a.payload as { rects?: { x0: number; y0: number; x1: number; y1: number }[] }).rects ?? []);
  const noteCount = annotations.filter(
    (a) => a.annotation_type === "note" && a.page === currentPage,
  ).length;

  return (
    <div className="flex h-full min-h-[32rem] flex-col rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
      <PdfSearchPanel pagesText={pagesText} onMatch={setSearchMatch} onJump={goto} />
      <div className="flex flex-wrap items-center gap-1.5 border-b border-[var(--border-subtle)] px-3 py-2 text-xs text-[var(--text-secondary)]">
        <button
          type="button"
          aria-label="Previous page"
          disabled={currentPage <= 1}
          onClick={() => goto(currentPage - 1)}
          className="rounded-md p-1.5 hover:bg-[var(--bg-hover)] disabled:opacity-40"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="flex items-center gap-1">
          <input
            aria-label="Jump to page"
            type="number"
            min={1}
            max={pageCount || 1}
            value={currentPage}
            onChange={(e) => goto(Number(e.target.value) || 1)}
            className="w-12 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-app)] px-1 py-0.5 text-center text-xs text-[var(--text-primary)]"
          />
          <span>/ {pageCount}</span>
        </span>
        <button
          type="button"
          aria-label="Next page"
          disabled={currentPage >= pageCount}
          onClick={() => goto(currentPage + 1)}
          className="rounded-md p-1.5 hover:bg-[var(--bg-hover)] disabled:opacity-40"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
        <span className="mx-1 h-4 w-px bg-[var(--border-subtle)]" />
        <button
          type="button"
          aria-label="Zoom out"
          onClick={() => zoom(1 / ZOOM_STEP)}
          className="rounded-md p-1.5 hover:bg-[var(--bg-hover)]"
        >
          <Minus className="h-4 w-4" />
        </button>
        <span className="w-12 text-center">{Math.round(currentScale * 100)}%</span>
        <button
          type="button"
          aria-label="Zoom in"
          onClick={() => zoom(ZOOM_STEP)}
          className="rounded-md p-1.5 hover:bg-[var(--bg-hover)]"
        >
          <Plus className="h-4 w-4" />
        </button>
        <button
          type="button"
          aria-label="Fit width"
          onClick={() => changeFit("width")}
          className={cn(
            "flex items-center gap-1 rounded-md px-2 py-1 hover:bg-[var(--bg-hover)]",
            currentFit === "width" && "bg-[var(--accent-subtle)] text-[var(--accent)]",
          )}
        >
          <Scissors className="h-3.5 w-3.5" /> Fit width
        </button>
        <button
          type="button"
          aria-label="Fit page"
          onClick={() => changeFit("page")}
          className={cn(
            "flex items-center gap-1 rounded-md px-2 py-1 hover:bg-[var(--bg-hover)]",
            currentFit === "page" && "bg-[var(--accent-subtle)] text-[var(--accent)]",
          )}
        >
          <Maximize className="h-3.5 w-3.5" /> Fit page
        </button>
        <span className="mx-1 h-4 w-px bg-[var(--border-subtle)]" />
        <button
          type="button"
          aria-label={bookmarkFor ? "Remove bookmark" : "Bookmark this page"}
          onClick={() => onToggleBookmark(currentPage)}
          className={cn(
            "flex items-center gap-1 rounded-md px-2 py-1 hover:bg-[var(--bg-hover)]",
            bookmarkFor && "bg-[var(--warning-subtle)] text-[var(--warning)]",
          )}
        >
          <Bookmark className="h-3.5 w-3.5" />
          {bookmarkFor ? "Bookmarked" : "Bookmark"}
        </button>
      </div>

      {error ? (
        <p role="alert" className="m-4 rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
          {error}
        </p>
      ) : (
        <div
          ref={containerRef}
          className="relative flex-1 overflow-auto bg-[var(--bg-app)] p-3"
          data-testid="pdf-page-area"
        >
          <div className="relative mx-auto w-fit shadow-sm">
            <canvas ref={canvasRef} aria-label={`Page ${currentPage} of ${fileName}`} />
            <svg
              className="pointer-events-none absolute inset-0 h-full w-full"
              aria-hidden="true"
            >
              {highlightRects.map((rect, index) => (
                <rect
                  key={`hl-${index}`}
                  x={rect.x0 * currentScale}
                  y={rect.y0 * currentScale}
                  width={(rect.x1 - rect.x0) * currentScale}
                  height={(rect.y1 - rect.y0) * currentScale}
                  fill="var(--accent)"
                  opacity={0.25}
                />
              ))}
              {searchMatch && searchMatch.page === currentPage && (
                <g>
                  {searchMatch.rects.map((rect, index) => (
                    <rect
                      key={`sr-${index}`}
                      x={rect.x0 * currentScale}
                      y={rect.y0 * currentScale}
                      width={(rect.x1 - rect.x0) * currentScale}
                      height={(rect.y1 - rect.y0) * currentScale}
                      fill="var(--warning)"
                      opacity={0.4}
                    />
                  ))}
                </g>
              )}
            </svg>
            {noteCount > 0 && (
              <span
                className="absolute left-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--warning)] text-white"
                title={`${noteCount} note(s) on this page`}
              >
                <StickyNote className="h-3 w-3" />
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

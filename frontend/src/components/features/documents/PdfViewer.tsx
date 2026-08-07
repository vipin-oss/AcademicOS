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
}

export function PdfViewer({
  documentId,
  fileName,
  annotations,
  onTextReady,
  onToggleBookmark,
  pagesText = [],
  onPdfReady,
}: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [page, setPage] = useState(1);
  const [scale, setScale] = useState(1);
  const [searchMatch, setSearchMatch] = useState<PdfSearchMatch | null>(null);
  const [fitMode, setFitMode] = useState<"width" | "page" | "custom">("width");
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const scaleRef = useRef<number>(1);
  scaleRef.current = scale;
  const fitModeRef = useRef<typeof fitMode>("width");
  fitModeRef.current = fitMode;

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
        setPageCount(doc.numPages);
        onPdfReady?.(doc);
        setPage(1);
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
      const pageObj = await pdf.getPage(page);
      if (cancelled) return;
      const base = pageObj.getViewport({ scale: 1 });
      const container = containerRef.current;
      let effective = scale;
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
      setScale(effective);
    })();
    return () => {
      cancelled = true;
    };
  }, [pdfDoc, page, scale, fitMode]);

  const goto = useCallback((next: number) => {
    setPage(Math.min(Math.max(next, 1), pageCount || 1));
  }, [pageCount]);

  const zoom = useCallback((factor: number) => {
    setFitMode("custom");
    setScale((s) => Math.min(Math.max(s * factor, MIN_SCALE), MAX_SCALE));
  }, []);

  const bookmarkFor = annotations.find(
    (a) => a.annotation_type === "bookmark" && a.page === page,
  );
  const highlightRects = annotations
    .filter((a) => a.annotation_type === "highlight" && a.page === page)
    .flatMap((a) => (a.payload as { rects?: { x0: number; y0: number; x1: number; y1: number }[] }).rects ?? []);
  const noteCount = annotations.filter(
    (a) => a.annotation_type === "note" && a.page === page,
  ).length;

  return (
    <div className="flex h-full min-h-[32rem] flex-col rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
      <PdfSearchPanel pagesText={pagesText} onMatch={setSearchMatch} onJump={goto} />
      <div className="flex flex-wrap items-center gap-1.5 border-b border-[var(--border-subtle)] px-3 py-2 text-xs text-[var(--text-secondary)]">
        <button
          type="button"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => goto(page - 1)}
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
            value={page}
            onChange={(e) => goto(Number(e.target.value) || 1)}
            className="w-12 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-app)] px-1 py-0.5 text-center text-xs text-[var(--text-primary)]"
          />
          <span>/ {pageCount}</span>
        </span>
        <button
          type="button"
          aria-label="Next page"
          disabled={page >= pageCount}
          onClick={() => goto(page + 1)}
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
        <span className="w-12 text-center">{Math.round(scale * 100)}%</span>
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
          onClick={() => setFitMode("width")}
          className={cn(
            "flex items-center gap-1 rounded-md px-2 py-1 hover:bg-[var(--bg-hover)]",
            fitMode === "width" && "bg-[var(--accent-subtle)] text-[var(--accent)]",
          )}
        >
          <Scissors className="h-3.5 w-3.5" /> Fit width
        </button>
        <button
          type="button"
          aria-label="Fit page"
          onClick={() => setFitMode("page")}
          className={cn(
            "flex items-center gap-1 rounded-md px-2 py-1 hover:bg-[var(--bg-hover)]",
            fitMode === "page" && "bg-[var(--accent-subtle)] text-[var(--accent)]",
          )}
        >
          <Maximize className="h-3.5 w-3.5" /> Fit page
        </button>
        <span className="mx-1 h-4 w-px bg-[var(--border-subtle)]" />
        <button
          type="button"
          aria-label={bookmarkFor ? "Remove bookmark" : "Bookmark this page"}
          onClick={() => onToggleBookmark(page)}
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
            <canvas ref={canvasRef} aria-label={`Page ${page} of ${fileName}`} />
            <svg
              className="pointer-events-none absolute inset-0 h-full w-full"
              aria-hidden="true"
            >
              {highlightRects.map((rect, index) => (
                <rect
                  key={`hl-${index}`}
                  x={rect.x0 * scale}
                  y={rect.y0 * scale}
                  width={(rect.x1 - rect.x0) * scale}
                  height={(rect.y1 - rect.y0) * scale}
                  fill="var(--accent)"
                  opacity={0.25}
                />
              ))}
              {searchMatch && searchMatch.page === page && (
                <g>
                  {searchMatch.rects.map((rect, index) => (
                    <rect
                      key={`sr-${index}`}
                      x={rect.x0 * scale}
                      y={rect.y0 * scale}
                      width={(rect.x1 - rect.x0) * scale}
                      height={(rect.y1 - rect.y0) * scale}
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

"use client";

/**
 * Thumbnail sidebar (Sprint M10) — lazy-rendered page thumbnails with
 * virtual scrolling.
 *
 * Each page renders its thumbnail on demand (only the visible window
 * plus a small buffer are mounted), the current page is highlighted, and
 * clicking a thumbnail jumps the viewer to that page. The thumbnail
 * layer is rendered into an offscreen canvas at a fixed width so the
 * list scrolls smoothly even for large PDFs.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";

import { cn } from "@/lib/utils";

const THUMB_WIDTH = 96;
const BUFFER = 3;

export interface ThumbnailSidebarProps {
  pdfDoc: PDFDocumentProxy | null;
  currentPage: number;
  onJump: (page: number) => void;
}

export function ThumbnailSidebar({ pdfDoc, currentPage, onJump }: ThumbnailSidebarProps) {
  const [pageCount, setPageCount] = useState(0);
  const [scrollTop, setScrollTop] = useState(0);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const heightsRef = useRef<number[]>([]);

  useEffect(() => {
    setPageCount(pdfDoc?.numPages ?? 0);
    heightsRef.current = [];
  }, [pdfDoc]);

  const measure = useCallback((page: number, height: number) => {
    heightsRef.current[page - 1] = height;
  }, []);

  const estimated = 150; // px per thumbnail until measured
  const totalHeight = Array.from(
    { length: pageCount },
    (_, i) => heightsRef.current[i] ?? estimated,
  ).reduce((a, b) => a + b, 0);
  const offsets: number[] = [];
  let acc = 0;
  for (let i = 0; i < pageCount; i += 1) {
    offsets.push(acc);
    acc += heightsRef.current[i] ?? estimated;
  }

  const start = Math.max(0, Math.floor(scrollTop / estimated) - BUFFER);
  const end = Math.min(pageCount, Math.ceil((scrollTop + 600) / estimated) + BUFFER);
  const visible: number[] = [];
  for (let i = start; i < end; i += 1) visible.push(i + 1);

  return (
    <aside
      aria-label="Page thumbnails"
      className="hidden w-28 shrink-0 flex-col overflow-hidden border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] lg:flex"
    >
      <div className="border-b border-[var(--border-subtle)] px-2 py-2 text-center text-xs font-medium text-[var(--text-secondary)]">
        Pages
      </div>
      <div
        ref={scrollRef}
        onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
        className="flex-1 overflow-y-auto px-2 py-2"
        style={{ height: "100%" }}
      >
        <div style={{ height: totalHeight, position: "relative" }}>
          {visible.map((page) => (
            <ThumbnailItem
              key={page}
              page={page}
              pdfDoc={pdfDoc}
              top={offsets[page - 1]}
              active={page === currentPage}
              onJump={onJump}
              onMeasure={measure}
            />
          ))}
        </div>
      </div>
    </aside>
  );
}

function ThumbnailItem({
  page,
  pdfDoc,
  top,
  active,
  onJump,
  onMeasure,
}: {
  page: number;
  pdfDoc: PDFDocumentProxy | null;
  top: number;
  active: boolean;
  onJump: (page: number) => void;
  onMeasure: (page: number, height: number) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!pdfDoc) return;
    const render = async () => {
      const pageObj = await pdfDoc.getPage(page);
      if (cancelled) return;
      const base = pageObj.getViewport({ scale: 1 });
      const scale = THUMB_WIDTH / base.width;
      const viewport = pageObj.getViewport({ scale });
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      onMeasure(page, canvas.height + 8);
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      await pageObj.render({ canvasContext: ctx, viewport }).promise;
    };
    void render();
    return () => {
      cancelled = true;
    };
  }, [pdfDoc, page, onMeasure]);

  return (
    <button
      type="button"
      aria-label={`Go to page ${page}`}
      aria-current={active ? "page" : undefined}
      onClick={() => onJump(page)}
      className={cn(
        "absolute left-0 right-0 flex justify-center rounded-md p-1 transition-colors",
        active ? "bg-[var(--accent-subtle)] ring-1 ring-[var(--accent)]" : "hover:bg-[var(--bg-hover)]",
      )}
      style={{ top }}
    >
      <canvas ref={canvasRef} className="rounded-sm bg-white shadow-sm" />
      <span className="sr-only">Page {page}</span>
    </button>
  );
}

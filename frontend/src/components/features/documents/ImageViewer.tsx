"use client";

/**
 * Image viewer (Sprint M10) — PNG / JPG / JPEG / TIFF / SVG.
 *
 * Zoom (in/out, percentage), pan (drag to move, or scroll within the
 * padded canvas), fit width and fit screen modes. TIFF is rendered via
 * the browser's native decoder when supported (image/tiff) — otherwise
 * the download fallback is offered.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Download, Maximize, Minus, Move, Plus, Scissors } from "lucide-react";

import { api, toErrorMessage } from "@/lib/api/client";
import { downloadDocument } from "@/lib/documents/download";
import { cn } from "@/lib/utils";

const MIN_SCALE = 0.1;
const MAX_SCALE = 8;

export function ImageViewer({ documentId, fileName }: { documentId: string; fileName: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [scale, setScale] = useState(1);
  const [fit, setFit] = useState<"width" | "screen" | "custom">("width");
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; panX: number; panY: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setError(null);
    api
      .getBlob(`/documents/${documentId}/download`, { signal: controller.signal })
      .then((blob) => {
        if (cancelled) return;
        setUrl(URL.createObjectURL(blob));
      })
      .catch((err) => {
        if (err instanceof Error && err.name === "AbortError") return;
        setError(toErrorMessage(err, "The image could not be loaded."));
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [documentId]);

  const download = useCallback(async () => {
    setDownloading(true);
    try {
      await downloadDocument({ id: documentId, file_name: fileName } as never);
    } catch (err) {
      setError(toErrorMessage(err, "Download failed."));
    } finally {
      setDownloading(false);
    }
  }, [documentId, fileName]);

  const zoom = useCallback((factor: number) => {
    setFit("custom");
    setScale((s) => Math.min(Math.max(s * factor, MIN_SCALE), MAX_SCALE));
    setPan({ x: 0, y: 0 });
  }, []);

  const fitWidth = useCallback(() => {
    setFit("width");
    setPan({ x: 0, y: 0 });
  }, []);

  const fitScreen = useCallback(() => {
    setFit("screen");
    setPan({ x: 0, y: 0 });
  }, []);

  const onDragStart = useCallback((e: React.MouseEvent) => {
    dragRef.current = { startX: e.clientX, startY: e.clientY, panX: pan.x, panY: pan.y };
    e.preventDefault();
  }, [pan]);

  const onDragMove = useCallback((e: React.MouseEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    setPan({ x: drag.panX + (e.clientX - drag.startX), y: drag.panY + (e.clientY - drag.startY) });
  }, []);

  const onDragEnd = useCallback(() => {
    dragRef.current = null;
  }, []);

  // Compute the rendered size for fit modes.
  const [rendered, setRendered] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {
    const img = imgRef.current;
    const container = containerRef.current;
    if (!img || !container) return;
    if (img.complete) {
      setRendered({ w: img.naturalWidth, h: img.naturalHeight });
    } else {
      img.onload = () => setRendered({ w: img.naturalWidth, h: img.naturalHeight });
    }
  }, [url]);

  const effectiveScale =
    fit === "width" && rendered && containerRef.current
      ? Math.max((containerRef.current.clientWidth - 32) / rendered.w, MIN_SCALE)
      : fit === "screen" && rendered && containerRef.current
        ? Math.max(
            Math.min(
              (containerRef.current.clientWidth - 32) / rendered.w,
              (containerRef.current.clientHeight - 32) / rendered.h,
            ),
            MIN_SCALE,
          )
        : scale;

  return (
    <div className="flex h-full min-h-[28rem] flex-col rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
      <div className="flex items-center gap-1.5 border-b border-[var(--border-subtle)] px-3 py-2 text-xs text-[var(--text-secondary)]">
        <button type="button" aria-label="Zoom out" onClick={() => zoom(1 / 1.25)} className="rounded-md p-1.5 hover:bg-[var(--bg-hover)]">
          <Minus className="h-4 w-4" />
        </button>
        <span className="w-14 text-center">{Math.round(effectiveScale * 100)}%</span>
        <button type="button" aria-label="Zoom in" onClick={() => zoom(1.25)} className="rounded-md p-1.5 hover:bg-[var(--bg-hover)]">
          <Plus className="h-4 w-4" />
        </button>
        <span className="mx-1 h-4 w-px bg-[var(--border-subtle)]" />
        <button
          type="button"
          onClick={fitWidth}
          className={cn("flex items-center gap-1 rounded-md px-2 py-1 hover:bg-[var(--bg-hover)]", fit === "width" && "bg-[var(--accent-subtle)] text-[var(--accent)]")}
        >
          <Scissors className="h-3.5 w-3.5" /> Fit width
        </button>
        <button
          type="button"
          onClick={fitScreen}
          className={cn("flex items-center gap-1 rounded-md px-2 py-1 hover:bg-[var(--bg-hover)]", fit === "screen" && "bg-[var(--accent-subtle)] text-[var(--accent)]")}
        >
          <Maximize className="h-3.5 w-3.5" /> Fit screen
        </button>
        <span className="ml-auto flex items-center gap-1 text-[var(--text-tertiary)]">
          <Move className="h-3.5 w-3.5" /> Drag to pan
        </span>
      </div>

      <div
        ref={containerRef}
        className="relative flex-1 overflow-hidden bg-[var(--bg-app)]"
        onMouseDown={onDragStart}
        onMouseMove={onDragMove}
        onMouseUp={onDragEnd}
        onMouseLeave={onDragEnd}
      >
        {error ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center">
            <p role="alert" className="max-w-md rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
              {error}
            </p>
            <button
              type="button"
              onClick={() => void download()}
              disabled={downloading}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:opacity-60"
            >
              <Download className="h-4 w-4" /> {downloading ? "Downloading…" : "Download file"}
            </button>
          </div>
        ) : url ? (
          <div
            className="absolute"
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px)`,
              left: "50%",
              top: "50%",
              marginLeft: `${(-(rendered?.w ?? 0) * effectiveScale) / 2}px`,
              marginTop: `${(-(rendered?.h ?? 0) * effectiveScale) / 2}px`,
            }}
          >
            <img
              ref={imgRef}
              src={url}
              alt={fileName}
              draggable={false}
              onError={() => setError("This image format cannot be displayed in the browser.")}
              className="select-none shadow-sm"
              style={{ width: (rendered?.w ?? 0) * effectiveScale, height: (rendered?.h ?? 0) * effectiveScale }}
            />
          </div>
        ) : (
          <p className="absolute inset-0 flex items-center justify-center text-sm text-[var(--text-tertiary)]">Loading image…</p>
        )}
      </div>
    </div>
  );
}

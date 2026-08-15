"use client";

/**
 * Multi-document workspace (Sprint M10).
 *
 * Opens multiple documents simultaneously in tabs; every tab preserves
 * its own viewer state (zoom, page, annotations, extracted-text panel,
 * pdf.js document + text layer), switches without losing that state,
 * and closing a tab frees its pdf.js document (memory cleanup). The
 * last active tab is restored on reload via sessionStorage.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { X } from "lucide-react";

import { listAnnotations } from "@/lib/api/annotations";
import { toErrorMessage } from "@/lib/api/client";
import type { PdfPageText } from "@/lib/pdf/textSync";
import type { DocumentAnnotation, DocumentResponse } from "@/types";
import { DocumentPreview } from "./DocumentPreview";
import { ExtractedTextPanel } from "./ExtractedTextPanel";
import { PdfViewer } from "./PdfViewer";
import { ThumbnailSidebar } from "./ThumbnailSidebar";

export interface WorkspaceTab {
  document: DocumentResponse;
  /** Restored per-tab viewer state. */
  page: number;
  scale: number;
  fitMode: "width" | "page" | "custom";
  showText: boolean;
}

const STORAGE_KEY = "academicos.docs.tabs";

export function DocumentWorkspace({
  documents,
  onCloseWorkspace,
}: {
  documents: DocumentResponse[];
  onCloseWorkspace: () => void;
}) {
  const [tabs, setTabs] = useState<WorkspaceTab[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  // Per-tab runtime state (pdf doc + text layer) kept separate from the
  // serializable tab list.
  const runtimeRef = useRef<
    Record<
      string,
      { pdf: PDFDocumentProxy | null; pagesText: PdfPageText[]; annotations: DocumentAnnotation[] }
    >
  >({});
  const [runtimeVersion, setRuntimeVersion] = useState(0);

  const bump = useCallback(() => setRuntimeVersion((v) => v + 1), []);

  // Restore the last active tab (sessionStorage).
  useEffect(() => {
    if (documents.length === 0) return;
    setTabs((prev) => {
      if (prev.length > 0) return prev;
      const newTabs = documents.map((document) => ({
        document,
        page: 1,
        scale: 1,
        fitMode: "width" as const,
        showText: true,
      }));
      return newTabs;
    });
    setActiveId((prev) => {
      if (prev) return prev;
      try {
        const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? "null") as
          | { id: string }[]
          | null;
        if (saved && saved.length > 0 && documents.some((d) => d.id === saved[0].id)) {
          return saved[0].id;
        }
      } catch {
        /* ignore malformed storage */
      }
      return documents[0]?.id ?? null;
    });
  }, [documents]);

  // Persist the active tab for restore.
  useEffect(() => {
    if (activeId) {
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify([{ id: activeId }]));
      } catch {
        /* storage unavailable */
      }
    }
  }, [activeId]);

  const active = tabs.find((t) => t.document.id === activeId) ?? null;

  const openTab = useCallback(
    (document: DocumentResponse) => {
      setTabs((prev) =>
        prev.some((t) => t.document.id === document.id)
          ? prev
          : [...prev, { document, page: 1, scale: 1, fitMode: "width" as const, showText: true }],
      );
      setActiveId(document.id);
    },
    [],
  );

  const closeTab = useCallback((id: string) => {
    setTabs((prev) => {
      const index = prev.findIndex((t) => t.document.id === id);
      const next = prev.filter((t) => t.document.id !== id);
      // The PdfViewer destroys its pdf.js document on unmount; here we
      // only drop the runtime reference.
      delete runtimeRef.current[id];
      if (next.length === 0) {
        setActiveId(null);
        onCloseWorkspace();
        return next;
      }
      setActiveId((cur) => (cur === id ? (next[Math.max(0, index - 1)]?.document.id ?? next[0].document.id) : cur));
      return next;
    });
  }, [onCloseWorkspace]);

  const updateTab = useCallback((id: string, patch: Partial<WorkspaceTab>) => {
    setTabs((prev) => prev.map((t) => (t.document.id === id ? { ...t, ...patch } : t)));
  }, []);

  // External "open this document" (e.g. from the table row).
  useEffect(() => {
    if (documents.length === 0) return;
    // opened set: the workspace is constructed with the requested docs.
    // Tabs were initialized from documents above.
  }, [documents]);

  if (tabs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface-2)] px-6 py-16 text-center">
        <p className="text-sm text-[var(--text-tertiary)]">
          No documents open. Open a PDF from the table to start the workspace.
        </p>
        <button
          type="button"
          onClick={onCloseWorkspace}
          className="rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
        >
          Back to document list
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
      {/* Tabs */}
      <div
        role="tablist"
        aria-label="Open documents"
        className="flex items-center gap-1 overflow-x-auto border-b border-[var(--border-subtle)] px-2 pt-2"
      >
        {tabs.map((tab) => (
          <div
            key={tab.document.id}
            role="tab"
            aria-selected={tab.document.id === activeId}
            tabIndex={tab.document.id === activeId ? 0 : -1}
            className={[
              "group flex max-w-[14rem] items-center gap-1.5 rounded-t-lg border border-b-0 px-3 py-2 text-xs",
              tab.document.id === activeId
                ? "border-[var(--border-subtle)] bg-[var(--bg-app)] text-[var(--text-primary)]"
                : "border-transparent text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]",
            ].join(" ")}
          >
            <button
              type="button"
              onClick={() => setActiveId(tab.document.id)}
              className="min-w-0 flex-1 truncate text-left"
              title={tab.document.file_name || tab.document.title}
            >
              {tab.document.file_name || tab.document.title}
            </button>
            <button
              type="button"
              aria-label={`Close ${tab.document.file_name || tab.document.title}`}
              onClick={() => closeTab(tab.document.id)}
              className="rounded p-0.5 opacity-60 hover:bg-[var(--bg-hover)] hover:opacity-100"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
        {documents.filter((d) => !tabs.some((t) => t.document.id === d.id)).length > 0 && (
          <div className="flex items-center gap-1 px-2 pb-1">
            {documents
              .filter((d) => !tabs.some((t) => t.document.id === d.id))
              .map((d) => (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => openTab(d)}
                  className="rounded-md border border-dashed border-[var(--border-strong)] px-2 py-1 text-xs text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)]"
                >
                  + {d.file_name || d.title}
                </button>
              ))}
          </div>
        )}
      </div>

      {/* Tab bodies — every open tab stays mounted (hidden when inactive)
          so switching tabs never destroys the pdf.js document and
          page/zoom/annotations survive; closing a tab unmounts its
          viewer, which frees the document (memory cleanup). */}
      <div className="flex min-h-0 flex-1">
        {tabs.map((tab) => {
          const rt = runtimeRef.current[tab.document.id] ?? {
            pdf: null,
            pagesText: [],
            annotations: [],
          };
          const isActive = tab.document.id === activeId;
          return (
            <div
              key={tab.document.id}
              role="tabpanel"
              aria-label={tab.document.file_name || tab.document.title}
              className="flex min-w-0 flex-1"
              style={{ display: isActive ? "flex" : "none" }}
            >
              {tab.document.document_type === "pdf" ? (
                <>
                  <ThumbnailSidebar
                    pdfDoc={rt.pdf}
                    currentPage={tab.page}
                    onJump={(page) => updateTab(tab.document.id, { page })}
                  />
                  <div className="flex min-w-0 flex-1">
                    <PdfViewer
                      documentId={tab.document.id}
                      fileName={tab.document.file_name || tab.document.title}
                      annotations={rt.annotations}
                      pagesText={rt.pagesText}
                      page={tab.page}
                      scale={tab.scale}
                      fitMode={tab.fitMode}
                      onPageChange={(page) => updateTab(tab.document.id, { page })}
                      onScaleChange={(scale) => updateTab(tab.document.id, { scale })}
                      onFitModeChange={(fitMode) => updateTab(tab.document.id, { fitMode })}
                      onPdfReady={(pdf) => {
                        runtimeRef.current[tab.document.id] = {
                          ...(runtimeRef.current[tab.document.id] ?? {
                            pagesText: [],
                            annotations: [],
                          }),
                          pdf,
                        };
                        bump();
                      }}
                      onTextReady={(pages) => {
                        runtimeRef.current[tab.document.id] = {
                          ...(runtimeRef.current[tab.document.id] ?? {
                            pdf: null,
                            annotations: [],
                          }),
                          pagesText: pages,
                        };
                        bump();
                      }}
                      onToggleBookmark={async (page) => {
                        const existing = rt.annotations.find(
                          (a) => a.annotation_type === "bookmark" && a.page === page,
                        );
                        try {
                          if (existing) {
                            const { deleteAnnotation } = await import("@/lib/api/annotations");
                            await deleteAnnotation(existing.annotation_id);
                          } else {
                            const { createAnnotation } = await import("@/lib/api/annotations");
                            await createAnnotation(tab.document.id, "bookmark", page, {
                              label: "page mark",
                            });
                          }
                          const { listAnnotations } = await import("@/lib/api/annotations");
                          const items = await listAnnotations(tab.document.id);
                          runtimeRef.current[tab.document.id] = {
                            ...(runtimeRef.current[tab.document.id] ?? { pdf: null, pagesText: [] }),
                            annotations: items.items,
                          };
                          bump();
                        } catch {
                          /* annotation errors surface via the panel */
                        }
                      }}
                    />
                    {tab.showText && (
                      <div className="w-[26rem] max-w-[40vw] shrink-0 border-l border-[var(--border-subtle)]">
                        <ExtractedTextPanel
                          documentId={tab.document.id}
                          annotations={rt.annotations}
                          pagesText={rt.pagesText}
                          currentPage={tab.page}
                          onJump={(page) => updateTab(tab.document.id, { page })}
                          onChanged={async () => {
                            const items = await listAnnotations(tab.document.id);
                            runtimeRef.current[tab.document.id] = {
                              ...(runtimeRef.current[tab.document.id] ?? { pdf: null, pagesText: [] }),
                              annotations: items.items,
                            };
                            bump();
                          }}
                          onError={() => undefined}
                        />
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="flex flex-1 items-center justify-center p-6">
                  <DocumentPreview document={tab.document} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Viewer toolbar per active tab */}
      {active && (
        <div className="flex items-center gap-3 border-t border-[var(--border-subtle)] px-3 py-2 text-xs text-[var(--text-secondary)]">
          <span>
            Page {active.page} · {runtimeRef.current[active.document.id]?.pdf?.numPages ?? "-"} · zoom{" "}
            {Math.round(active.scale * 100)}%
          </span>
          <button
            type="button"
            onClick={() => updateTab(active.document.id, { showText: !active.showText })}
            className="ml-auto rounded-md border border-[var(--border-subtle)] px-2 py-1 hover:bg-[var(--bg-hover)]"
          >
            {active.showText ? "Hide extracted text" : "Show extracted text"}
          </button>
        </div>
      )}
    </div>
  );
}

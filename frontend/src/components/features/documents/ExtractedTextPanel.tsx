"use client";

/**
 * Extracted-text panel (Sprint M10) — the right half of the side-by-side
 * viewer. Shows the text the intake pipeline extracted from the original
 * document, lets the user SELECT text and turn it into a PDF highlight
 * (text synchronization: the selection is matched against the pdf.js
 * text layer and its approximate region is persisted as an annotation),
 * adds page-anchored notes, and lists every annotation with delete.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Highlighter, Plus, StickyNote, Trash2 } from "lucide-react";

import {
  createAnnotation,
  deleteAnnotation,
  getExtractedText,
} from "@/lib/api/annotations";
import { SelectionActions, type SelectionActionHandler } from "./SelectionActions";
import { toErrorMessage } from "@/lib/api/client";
import { findTextHighlight, type PdfPageText } from "@/lib/pdf/textSync";
import type { DocumentAnnotation } from "@/types";
import { cn } from "@/lib/utils";

export interface ExtractedTextPanelProps extends SelectionActionHandler {
  documentId: string;
  annotations: DocumentAnnotation[];
  pagesText: PdfPageText[];
  /** The page currently shown in the viewer (default for notes/jumps). */
  currentPage: number;
  onJump: (page: number) => void;
  onChanged: () => void;
  onError: (message: string | null) => void;
}

export function ExtractedTextPanel({
  documentId,
  annotations,
  pagesText,
  currentPage,
  onJump,
  onChanged,
  onError,
  onLlmAction,
}: ExtractedTextPanelProps) {
  const [text, setText] = useState<string | null>(null);
  const [textError, setTextError] = useState<string | null>(null);
  const [selection, setSelection] = useState("");
  const [noteOpen, setNoteOpen] = useState(false);
  const [notePage, setNotePage] = useState(currentPage);
  const [noteText, setNoteText] = useState("");
  const [busy, setBusy] = useState(false);
  const textRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    getExtractedText(documentId)
      .then((res) => {
        if (!cancelled) {
          setText(res.text);
          setTextError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setTextError(toErrorMessage(err, "No extracted text available."));
          setText(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  // Track the selection inside the extracted-text pane.
  const captureSelection = useCallback(() => {
    const el = textRef.current;
    if (!el) return;
    const selected = el.value.slice(el.selectionStart ?? 0, el.selectionEnd ?? 0).trim();
    setSelection(selected);
  }, []);

  const highlightSelection = useCallback(async () => {
    if (!selection) return;
    const match = findTextHighlight(pagesText, selection);
    if (!match) {
      onError("The selected text was not found in the PDF text layer.");
      return;
    }
    setBusy(true);
    onError(null);
    try {
      await createAnnotation(documentId, "highlight", match.page, {
        rects: match.rects,
        text: selection,
      });
      onChanged();
      onJump(match.page);
      setSelection("");
    } catch (err) {
      onError(toErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [selection, pagesText, documentId, onChanged, onJump, onError]);

  const saveNote = useCallback(async () => {
    if (!noteText.trim()) return;
    setBusy(true);
    onError(null);
    try {
      await createAnnotation(documentId, "note", Math.max(1, notePage), {
        text: noteText.trim(),
      });
      setNoteOpen(false);
      setNoteText("");
      onChanged();
    } catch (err) {
      onError(toErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [documentId, notePage, noteText, onChanged, onError]);

  const remove = useCallback(
    async (annotationId: string) => {
      setBusy(true);
      onError(null);
      try {
        await deleteAnnotation(annotationId);
        onChanged();
      } catch (err) {
        onError(toErrorMessage(err));
      } finally {
        setBusy(false);
      }
    },
    [onChanged, onError],
  );

  const notes = annotations.filter((a) => a.annotation_type === "note");
  const bookmarks = annotations.filter((a) => a.annotation_type === "bookmark");
  const highlightCount = annotations.filter((a) => a.annotation_type === "highlight").length;

  return (
    <div className="flex h-full min-h-[32rem] flex-col rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-3 py-2 text-xs text-[var(--text-secondary)]">
        <span className="font-medium text-[var(--text-primary)]">Extracted text</span>
        <span>
          {highlightCount} highlight(s) · {notes.length} note(s) · {bookmarks.length} bookmark(s)
        </span>
      </div>

      <div className="relative flex-1 overflow-hidden p-3">
        {textError ? (
          <p className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-3 py-2 text-sm text-[var(--text-tertiary)]">
            {textError}
          </p>
        ) : text === null ? (
          <p className="text-sm text-[var(--text-tertiary)]">Loading extracted text…</p>
        ) : (
          <textarea
            ref={textRef}
            value={text}
            readOnly
            onSelect={captureSelection}
            onMouseUp={captureSelection}
            onKeyUp={captureSelection}
            aria-label="Extracted text"
            className="h-full w-full resize-none bg-transparent text-sm leading-relaxed text-[var(--text-primary)] focus:outline-none"
          />
        )}
      </div>

      <SelectionActions
        selection={selection}
        currentPage={currentPage}
        onLlmAction={onLlmAction}
        onHighlight={(text) => {
          setSelection(text);
          void highlightSelection();
        }}
        onCreateNote={(text) => {
          setNotePage(currentPage);
          setNoteText(text);
          setNoteOpen(true);
        }}
        onBookmark={(page) => {
          void createAnnotation(documentId, "bookmark", page, { label: "page mark" })
            .then(onChanged)
            .catch((err) => onError(toErrorMessage(err)));
        }}
      />
      <div className="flex flex-wrap items-center gap-2 border-t border-[var(--border-subtle)] px-3 py-2 text-xs">
        <button
          type="button"
          disabled={!selection || busy}
          onClick={() => void highlightSelection()}
          className={cn(
            "flex items-center gap-1 rounded-md px-2.5 py-1.5 font-semibold",
            selection
              ? "bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]"
              : "cursor-not-allowed bg-[var(--bg-hover)] text-[var(--text-tertiary)]",
          )}
        >
          <Highlighter className="h-3.5 w-3.5" />
          {selection ? "Highlight selection" : "Select text to highlight"}
        </button>
        <button
          type="button"
          onClick={() => {
            setNotePage(currentPage);
            setNoteOpen((v) => !v);
          }}
          className="flex items-center gap-1 rounded-md border border-[var(--border-subtle)] px-2.5 py-1.5 font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
        >
          <StickyNote className="h-3.5 w-3.5" /> Add note
        </button>
      </div>

      {noteOpen && (
        <div className="flex items-center gap-2 border-t border-[var(--border-subtle)] px-3 py-2 text-xs">
          <input
            type="number"
            min={1}
            value={notePage}
            onChange={(e) => setNotePage(Number(e.target.value) || 1)}
            aria-label="Note page"
            className="w-14 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-app)] px-1.5 py-1 text-[var(--text-primary)]"
          />
          <input
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void saveNote();
            }}
            placeholder="Note text…"
            aria-label="Note text"
            className="min-w-0 flex-1 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1 text-[var(--text-primary)]"
          />
          <button
            type="button"
            disabled={busy || !noteText.trim()}
            onClick={() => void saveNote()}
            className="rounded-md bg-[var(--accent)] px-2 py-1 font-semibold text-white disabled:opacity-50"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      <div className="max-h-48 overflow-auto border-t border-[var(--border-subtle)] px-3 py-2 text-xs">
        {annotations.length === 0 && (
          <p className="text-[var(--text-tertiary)]">No annotations yet.</p>
        )}
        {annotations.map((annotation) => (
          <div
            key={annotation.annotation_id}
            className="flex items-start justify-between gap-2 py-1"
          >
            <button
              type="button"
              onClick={() => onJump(annotation.page)}
              className="min-w-0 flex-1 text-left hover:underline"
            >
              <span className="font-medium text-[var(--accent)]">p.{annotation.page}</span>{" "}
              <span className="text-[var(--text-secondary)]">
                {annotation.annotation_type === "highlight"
                  ? `highlight: ${(annotation.payload as { text?: string }).text ?? "—"}`
                  : annotation.annotation_type === "note"
                    ? `note: ${(annotation.payload as { text: string }).text}`
                    : `bookmark: ${(annotation.payload as { label?: string }).label ?? "page mark"}`}
              </span>
            </button>
            <button
              type="button"
              aria-label={`Delete ${annotation.annotation_type} on page ${annotation.page}`}
              onClick={() => void remove(annotation.annotation_id)}
              className="rounded p-1 text-[var(--text-tertiary)] hover:bg-[var(--danger-subtle)] hover:text-[var(--danger)]"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

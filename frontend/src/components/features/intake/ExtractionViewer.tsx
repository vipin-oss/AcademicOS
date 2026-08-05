"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Copy, Download, X } from "lucide-react";
import type { IntakeItem, IntakeSession } from "@/types";
import { useExtractedText } from "@/hooks/useExtractedText";
import {
  copyTextToClipboard,
  downloadBasename,
  downloadBlob,
  hasExtractedText,
  metadataJsonOf,
  noTextReason,
  EXTRACTION_PREVIEW_LIMIT,
} from "@/lib/intake/extraction";
import { ExtractionBadges } from "./ExtractionBadges";
import { ExtractionMetadataCard } from "./ExtractionMetadataCard";
import { ExtractedTextViewer, TextPane } from "./ExtractedTextViewer";
import { cn } from "@/lib/utils";

type TabKey = "metadata" | "preview" | "text";

const TABS: { key: TabKey; label: string }[] = [
  { key: "metadata", label: "Metadata" },
  { key: "preview", label: "Preview" },
  { key: "text", label: "Extracted text" },
];

/**
 * The M2 Part 2 extraction viewer: Metadata / Preview / Extracted-text tabs
 * for one staged file, rendered inline under the session's file table — the
 * user never leaves AcademicOS. Read-only end to end.
 *
 * Accessibility contract:
 * - labelled region (`aria-labelledby` the heading), heading receives focus
 *   on open, Escape asks the parent to close (and restore trigger focus);
 * - WAI-ARIA tabs: roving tabindex, Arrow keys / Home / End move between
 *   tabs, `aria-selected` + `aria-controls`/`aria-labelledby` wiring;
 * - all feedback (copied, loading, match counts) is announced via polite
 *   live regions; every control has a stable aria-label.
 */
export function ExtractionViewer({
  session,
  item,
  onClose,
}: {
  session: IntakeSession;
  item: IntakeItem;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<TabKey>("metadata");
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const wantsText = hasExtractedText(item);
  const { text, loading, error, unavailable, reload } = useExtractedText(
    session.id,
    item.id,
    wantsText,
  );

  // Focus the panel heading when the viewer opens (focus management).
  useEffect(() => {
    headingRef.current?.focus();
  }, [item.id]);

  // Newly selected file: land on the metadata tab again.
  useEffect(() => {
    setTab("metadata");
  }, [item.id]);

  const base = useMemo(() => downloadBasename(item), [item]);
  const stem = base.replace(/\.[^.]+$/, "");
  const textReady = text !== null;
  const textHasContent = textReady && (text as string).length > 0;
  const textActionsBlockedReason = !wantsText
    ? noTextReason(item)
    : loading
      ? "Text is loading…"
      : !textReady
        ? "Text is not loaded yet."
        : text === ""
          ? "The extracted text is empty."
          : null;

  const preview = item.extraction?.preview_text ?? null;
  const previewAvailable = typeof preview === "string" && preview.length > 0;

  const doCopy = async () => {
    if (!textReady || text === null) return;
    setCopyFailed(false);
    const ok = await copyTextToClipboard(text);
    if (ok) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } else {
      setCopyFailed(true);
    }
  };

  const doDownloadText = () => {
    if (!textReady || text === null) return;
    downloadBlob(
      `${stem}.extracted.txt`,
      new Blob([text], { type: "text/plain;charset=utf-8" }),
    );
  };

  const doDownloadMetadata = () => {
    downloadBlob(
      `${stem}.metadata.json`,
      new Blob([JSON.stringify(metadataJsonOf(session, item), null, 2)], {
        type: "application/json",
      }),
    );
  };

  const onTabKeyDown = (event: React.KeyboardEvent, index: number) => {
    let next: number | null = null;
    if (event.key === "ArrowRight") next = (index + 1) % TABS.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + TABS.length) % TABS.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = TABS.length - 1;
    if (next !== null) {
      event.preventDefault();
      setTab(TABS[next].key);
      tabRefs.current[next]?.focus();
    }
  };

  return (
    <section
      aria-label={`Extraction viewer for ${item.relative_path}`}
      aria-labelledby="extraction-viewer-heading"
      id="extraction-viewer"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          onClose();
        }
      }}
      className="flex flex-col gap-4 rounded-xl border border-[var(--accent)] bg-[var(--bg-surface)] p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2
              ref={headingRef}
              tabIndex={-1}
              id="extraction-viewer-heading"
              className="truncate text-sm font-semibold text-[var(--text-primary)] outline-none"
            >
              {item.relative_path}
            </h2>
            <ExtractionBadges item={item} size="xs" />
          </div>
          <p className="text-xs text-[var(--text-tertiary)]">
            extraction engine output — read-only
          </p>
          <span role="status" aria-live="polite" className="sr-only">
            {copied ? "Extracted text copied to the clipboard." : ""}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5" aria-label="Extraction actions">
          <button
            type="button"
            aria-label={`Copy extracted text of ${item.relative_path}`}
            title={textActionsBlockedReason ?? "Copy the complete extracted text"}
            disabled={textActionsBlockedReason !== null}
            onClick={() => void doCopy()}
            className="flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy text"}
          </button>
          <button
            type="button"
            aria-label={`Download extracted text of ${item.relative_path} (.txt)`}
            title={textActionsBlockedReason ?? "Download the complete extracted text as .txt"}
            disabled={textActionsBlockedReason !== null}
            onClick={doDownloadText}
            className="flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            Text (.txt)
          </button>
          <button
            type="button"
            aria-label={`Download extraction metadata of ${item.relative_path} (.json)`}
            title="Download the metadata and descriptor as .json"
            onClick={doDownloadMetadata}
            className="flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          >
            <Download className="h-3.5 w-3.5" />
            Metadata (.json)
          </button>
          <button
            type="button"
            aria-label="Close extraction viewer"
            onClick={onClose}
            className="flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          >
            <X className="h-3.5 w-3.5" />
            Close
          </button>
        </div>
      </div>
      {copyFailed && (
        <p role="alert" className="text-xs text-[var(--danger)]">
          Copy failed — the browser refused clipboard access. Select the text and copy it manually.
        </p>
      )}

      <div>
        <div
          role="tablist"
          aria-label="Extraction panels"
          className="flex gap-1 border-b border-[var(--border-subtle)]"
        >
          {TABS.map(({ key, label }, index) => (
            <button
              key={key}
              ref={(el) => {
                tabRefs.current[index] = el;
              }}
              type="button"
              role="tab"
              id={`extraction-tab-${key}`}
              aria-selected={tab === key}
              aria-controls={`extraction-panel-${key}`}
              tabIndex={tab === key ? 0 : -1}
              onClick={() => setTab(key)}
              onKeyDown={(event) => onTabKeyDown(event, index)}
              className={cn(
                "-mb-px border-b-2 px-3 py-1.5 text-sm",
                tab === key
                  ? "border-[var(--accent)] font-medium text-[var(--accent)]"
                  : "border-transparent text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        <div
          role="tabpanel"
          id={`extraction-panel-${tab}`}
          aria-labelledby={`extraction-tab-${tab}`}
          className="pt-3"
        >
          {tab === "metadata" && <ExtractionMetadataCard item={item} />}

          {tab === "preview" &&
            (previewAvailable ? (
              <div className="flex flex-col gap-2" aria-label="Preview panel">
                <TextPane
                  text={preview}
                  ariaLabel={`Preview of ${item.relative_path}`}
                  maxHeightClass="max-h-[18rem]"
                />
                <p className="text-xs text-[var(--text-tertiary)]">
                  First {Math.min(preview.length, EXTRACTION_PREVIEW_LIMIT)} of{" "}
                  {(item.extraction?.character_count ?? preview.length).toLocaleString()} characters
                  — exact engine output, nothing inferred.
                </p>
              </div>
            ) : (
              <p
                aria-label="Preview unavailable"
                className="rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface-2)] px-4 py-6 text-center text-sm text-[var(--text-tertiary)]"
              >
                No preview available — {noTextReason(item)}
              </p>
            ))}

          {tab === "text" &&
            (!wantsText || unavailable ? (
              <p
                aria-label="Extracted text unavailable"
                className="rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface-2)] px-4 py-6 text-center text-sm text-[var(--text-tertiary)]"
              >
                No extracted text to display — {noTextReason(item)}
              </p>
            ) : loading ? (
              <div className="flex flex-col gap-2" aria-label="Loading extracted text">
                <div className="h-4 w-40 animate-pulse rounded bg-[var(--bg-hover)]" />
                <div className="h-48 animate-pulse rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-hover)]" />
              </div>
            ) : error && !textReady ? (
              <div
                role="alert"
                className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--danger-subtle)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
              >
                <span>{error}</span>
                <button
                  type="button"
                  aria-label="Retry loading extracted text"
                  onClick={reload}
                  className="rounded-md border border-[var(--danger)] px-2 py-1 text-xs hover:bg-[var(--bg-surface)]"
                >
                  Retry
                </button>
              </div>
            ) : textHasContent ? (
              <ExtractedTextViewer text={text} itemLabel={item.relative_path} />
            ) : (
              // Loaded fine, but the engine honestly produced zero characters.
              <p
                aria-label="Extracted text unavailable"
                className="rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface-2)] px-4 py-6 text-center text-sm text-[var(--text-tertiary)]"
              >
                No extracted text to display — {noTextReason(item)}
              </p>
            ))}
        </div>
      </div>
    </section>
  );
}

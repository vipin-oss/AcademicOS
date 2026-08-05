/**
 * Intake M2 extraction viewer helpers — pure, deterministic, no fetching.
 *
 * Everything here *derives display state from the backend descriptor only*:
 * the engine output is never invented, and every derived state (matching the
 * backend's own doctrine) is disclosed in its aria-label/title.
 */
import type { IntakeExtractionDescriptor, IntakeItem, IntakeSession } from "@/types";
import type { ChipTone } from "./constants";

/** Mirror of the backend `PREVIEW_LIMIT` (dtos/extraction.py). */
export const EXTRACTION_PREVIEW_LIMIT = 500;

export type ExtractionBadgeKey =
  | "extracted"
  | "unsupported"
  | "needs_ocr"
  | "failed"
  | "queued";

export const EXTRACTION_BADGE_META: Record<
  ExtractionBadgeKey,
  { label: string; aria: string; tone: ChipTone }
> = {
  extracted: {
    label: "Extracted",
    aria: "Extraction: extracted",
    tone: "success",
  },
  unsupported: {
    label: "Unsupported",
    aria: "Extraction: unsupported format",
    tone: "muted",
  },
  needs_ocr: {
    label: "Needs OCR",
    aria: "Extraction: needs OCR — the file has no extractable text layer",
    tone: "warning",
  },
  failed: {
    label: "Failed",
    aria: "Extraction: failed",
    tone: "danger",
  },
  queued: {
    label: "Queued",
    aria: "Extraction: queued — the extract stage has not run for this file yet",
    tone: "accent",
  },
};

/**
 * Honest "needs OCR" derivation: a PDF whose engine round produced zero
 * characters has no embedded text layer (OCR itself is a later milestone —
 * the badge only reports the *absence of text*, never a promise).
 *
 * The discriminator is the descriptor's `format` ("pdf"), not `engine` — the
 * engine field names the reader library ("pypdf 5.1.0"), the format names
 * the parser family.
 */
export function needsOcr(item: IntakeItem): boolean {
  const ex = item.extraction;
  return (
    ex?.status === "extracted" &&
    ex.format === "pdf" &&
    (ex.character_count ?? 0) === 0
  );
}

/** Ordered badge set for one item (failed wins over descriptor states). */
export function extractionBadgesOf(item: IntakeItem): ExtractionBadgeKey[] {
  if (item.error !== null) {
    return item.extraction?.status === "extracted" && needsOcr(item)
      ? ["failed", "needs_ocr"]
      : ["failed"];
  }
  const ex = item.extraction;
  if (!ex) return ["queued"];
  if (ex.status === "unsupported") return ["unsupported"];
  return needsOcr(item) ? ["extracted", "needs_ocr"] : ["extracted"];
}

/** True when a GET on the raw-text endpoint is meaningful for this item. */
export function hasExtractedText(item: IntakeItem): boolean {
  return item.extraction?.status === "extracted" && item.extraction.text_key !== null;
}

/** Honest one-line reason there is no text/preview to show. */
export function noTextReason(item: IntakeItem): string {
  if (item.error !== null) return "Extraction failed for this file.";
  const ex = item.extraction;
  if (!ex) return "Extraction has not run for this file yet.";
  if (ex.status === "unsupported") {
    return "This file format is not supported by the extraction engine — no text was extracted.";
  }
  if ((ex.character_count ?? 0) === 0) {
    return ex.format === "pdf"
      ? "The PDF has no extractable text layer (it may be scanned images). OCR is not available yet."
      : "The extraction engine found no text in this file.";
  }
  return "The extracted text is not stored for this file.";
}

/** Fine-grained basename helper for download filenames (never a path). */
export function downloadBasename(item: IntakeItem): string {
  const base = item.title || item.relative_path.split("/").pop() || "item";
  return base.replace(/[^\w.\-() ]+/g, "_").trim() || "item";
}

/** The metadata download payload — the real descriptor plus item identity. */
export function metadataJsonOf(session: IntakeSession, item: IntakeItem): Record<string, unknown> {
  const ex: IntakeExtractionDescriptor | null = item.extraction;
  return {
    session_id: session.id,
    session_title: session.title,
    item: {
      id: item.id,
      relative_path: item.relative_path,
      filename: item.title,
      extension: item.extension,
      mime_type: item.mime_type,
      size_bytes: item.size_bytes,
      sha256: item.sha256,
      status: item.status,
      error: item.error,
    },
    extraction: ex,
    needs_ocr: needsOcr(item),
  };
}

/** Trigger a browser download for a Blob (frontend-only action). */
export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * Copy text to the clipboard. Uses the async Clipboard API when available
 * and falls back to a hidden textarea + execCommand; resolves false when the
 * environment refuses both (the caller then says "copy failed", honestly).
 */
export async function copyTextToClipboard(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through to the legacy path */
  }
  try {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  } catch {
    return false;
  }
}

/** Case-insensitive match segments for the search highlighter. */
export interface TextSegment {
  text: string;
  match: boolean;
}

function escapeRegExp(query: string): string {
  return query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Split `text` into matched/unmatched segments for highlighting.
 * Empty queries yield one plain segment; the split is deterministic and
 * never touches the backend.
 */
export function highlightSegments(text: string, query: string): TextSegment[] {
  const trimmed = query.trim();
  if (!trimmed || !text) return [{ text, match: false }];
  const re = new RegExp(escapeRegExp(trimmed), "gi");
  const segments: TextSegment[] = [];
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m[0].length === 0) break; // zero-width guard
    if (m.index > lastIndex) segments.push({ text: text.slice(lastIndex, m.index), match: false });
    segments.push({ text: m[0], match: true });
    lastIndex = m.index + m[0].length;
    if (segments.length > 10_000) break; // pathological input guard
  }
  if (lastIndex < text.length) segments.push({ text: text.slice(lastIndex), match: false });
  return segments;
}

/** Count of matched segments (same semantics as {@link highlightSegments}). */
export function countMatches(text: string, query: string): number {
  const trimmed = query.trim();
  if (!trimmed || !text) return 0;
  const re = new RegExp(escapeRegExp(trimmed), "gi");
  let count = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    count += 1;
    if (m[0].length === 0) break;
    if (count > 100_000) break;
  }
  return count;
}

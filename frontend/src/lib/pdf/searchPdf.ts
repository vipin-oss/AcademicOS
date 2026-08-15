/**
 * PDF full-text search (Sprint M10B).
 *
 * Pure, deterministic search over the pdf.js text layer: a normalized
 * case-insensitive (or case-sensitive) whole-word (or substring) scan of
 * every page's item text, returning each match's page, index and
 * covering item rectangles in PDF units (scale-independent, same shape
 * as `findTextHighlight`). The viewer iterates the matches with
 * next/previous and renders the current match's rectangles as a
 * highlight overlay.
 *
 * Words split across pdf.js items are rejoined: the items' text is
 * concatenated, a match may span an item boundary, and the rect list
 * covers every overlapping item.
 */

import type { PdfPageText, PdfRect } from "./textSync";

export interface PdfSearchMatch {
  /** 1-based page. */
  page: number;
  /** 0-based index in the page's concatenated (space-joined) text. */
  index: number;
  /** The matched text (original casing of the needle). */
  text: string;
  /** Covering rectangles in PDF units. */
  rects: PdfRect[];
}

export interface PdfSearchOptions {
  caseSensitive?: boolean;
  wholeWord?: boolean;
}

const normalize = (value: string, caseSensitive: boolean): string =>
  caseSensitive ? value : value.toLowerCase();

const isWordChar = (ch: string): boolean => /[A-Za-z0-9]/.test(ch);

/**
 * Find every occurrence of `needle` across the given pages.
 * `wholeWord` requires the match to be delimited by non-word characters
 * (or the string edges); matching is case-insensitive unless
 * `caseSensitive` is set. Returns matches in page order, then text
 * order. Empty needles return [].
 */
export function searchPdfText(
  pages: PdfPageText[],
  needle: string,
  options: PdfSearchOptions = {},
): PdfSearchMatch[] {
  const target = normalize(needle.trim(), options.caseSensitive ?? false);
  if (!target) return [];

  const matches: PdfSearchMatch[] = [];
  for (const { page, items } of pages) {
    // Concatenated text WITHOUT separators (so a needle spanning item
    // boundaries matches), plus per-item span boundaries in that string.
    let combined = "";
    const spans: { item: PdfPageText["items"][number]; start: number; end: number }[] = [];
    for (const item of items) {
      const text = normalize(item.str, options.caseSensitive ?? false);
      if (!text) continue;
      const start = combined.length;
      combined += text;
      spans.push({ item, start, end: start + text.length });
    }

    let from = 0;
    for (;;) {
      const index = combined.indexOf(target, from);
      if (index === -1) break;
      if (options.wholeWord) {
        const before = index === 0 ? "" : combined[index - 1];
        const after =
          index + target.length >= combined.length ? "" : combined[index + target.length];
        if (isWordChar(before) || isWordChar(after)) {
          from = index + 1;
          continue;
        }
      }
      const end = index + target.length;
      const rects: PdfRect[] = [];
      for (const span of spans) {
        const overlapStart = Math.max(index, span.start);
        const overlapEnd = Math.min(end, span.end);
        if (overlapStart >= overlapEnd) continue;
        const fraction = (overlapEnd - overlapStart) / (span.end - span.start);
        const [, , , , x, y] = span.item.transform;
        const height = span.item.height || 0;
        const width = (span.item.width || 0) * fraction;
        rects.push({ x0: x, y0: y - height, x1: x + width, y1: y });
      }
      if (rects.length > 0) {
        matches.push({ page, index, text: needle.trim(), rects });
      }
      from = end;
    }
  }
  return matches;
}

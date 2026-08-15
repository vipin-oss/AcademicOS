/**
 * PDF text synchronization (Sprint M10).
 *
 * Pure, deterministic mapping between the extracted text the user selects
 * and the approximate region in the original PDF. pdf.js exposes each
 * page's `textContent` as items with a string, a transform (e/f = baseline
 * x/y in PDF units) and a width/height — this module finds a normalized
 * needle inside the concatenated item text of a page and returns the
 * covering item rectangles in PDF units (scale-independent), so the viewer
 * can render highlights at any zoom level.
 */

export interface PdfTextItem {
  str: string;
  /** pdf.js text-item transform; indices 4/5 are the baseline x/y. */
  transform: number[];
  width: number;
  height: number;
}

export interface PdfPageText {
  /** 1-based page number. */
  page: number;
  items: PdfTextItem[];
}

export interface PdfRect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface HighlightMatch {
  page: number;
  rects: PdfRect[];
}

const norm = (value: string): string =>
  value.toLowerCase().replace(/\s+/g, " ").trim();

/**
 * Find the first occurrence of `needle` across the given pages and return
 * its approximate region: the page plus the covering item rectangles in
 * PDF units (the portion of each item's width that overlaps the match).
 * Returns null when the needle does not appear (or is empty).
 */
export function findTextHighlight(
  pages: PdfPageText[],
  needle: string,
): HighlightMatch | null {
  const target = norm(needle);
  if (!target) return null;

  for (const { page, items } of pages) {
    let combined = "";
    const spans: { item: PdfTextItem; start: number; end: number }[] = [];
    for (const item of items) {
      const text = norm(item.str);
      if (!text) continue;
      const start = combined.length;
      combined += text;
      combined += " "; // item separator — words split across items rejoin
      spans.push({ item, start, end: start + text.length });
    }

    const index = combined.indexOf(target);
    if (index === -1) continue;
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
    if (rects.length > 0) return { page, rects };
  }
  return null;
}

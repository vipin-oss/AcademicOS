import { describe, expect, it } from "vitest";
import { searchPdfText } from "@/lib/pdf/searchPdf";
import type { PdfPageText, PdfTextItem } from "@/lib/pdf/textSync";

function item(str: string, x: number, y: number, width: number): PdfTextItem {
  return { str, transform: [1, 0, 0, 1, x, y], width, height: 10 };
}

const page = (n: number, items: PdfTextItem[]): PdfPageText => ({ page: n, items });

describe("searchPdfText", () => {
  it("finds all occurrences across pages in order", () => {
    const pages = [
      page(1, [item("Waves propagate in media", 10, 700, 160)]),
      page(2, [item("more waves here", 10, 700, 100)]),
    ];
    const matches = searchPdfText(pages, "waves");
    expect(matches).toHaveLength(2);
    expect(matches[0].page).toBe(1);
    expect(matches[1].page).toBe(2);
    expect(matches[0].rects.length).toBe(1);
  });

  it("is case-insensitive by default and case-sensitive when asked", () => {
    const pages = [page(1, [item("Waves", 10, 700, 40)])];
    expect(searchPdfText(pages, "waves")).toHaveLength(1);
    expect(searchPdfText(pages, "waves", { caseSensitive: true })).toHaveLength(0);
    expect(searchPdfText(pages, "Waves", { caseSensitive: true })).toHaveLength(1);
  });

  it("supports whole-word matching", () => {
    const pages = [page(1, [item("the wave and the waves", 10, 700, 160)])];
    // whole-word: only the standalone "wave" matches ("waves" is a
    // different word); substring mode finds both.
    expect(searchPdfText(pages, "wave", { wholeWord: true })).toHaveLength(1);
    expect(searchPdfText(pages, "wave")).toHaveLength(2);
  });

  it("rejoins words split across items", () => {
    const pages = [
      page(1, [
        item("piezothermo", 10, 700, 80),
        item("elastic media", 90, 700, 90),
      ]),
    ];
    const matches = searchPdfText(pages, "piezothermoelastic");
    expect(matches).toHaveLength(1);
    expect(matches[0].rects.length).toBe(2);
  });

  it("returns [] for empty or missing needles", () => {
    const pages = [page(1, [item("waves", 10, 700, 40)])];
    expect(searchPdfText(pages, "")).toEqual([]);
    expect(searchPdfText(pages, "quantum")).toEqual([]);
    expect(searchPdfText([], "waves")).toEqual([]);
  });
});

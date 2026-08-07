import { describe, expect, it } from "vitest";
import {
  findTextHighlight,
  type PdfPageText,
  type PdfTextItem,
} from "@/lib/pdf/textSync";

function item(str: string, x: number, y: number, width: number): PdfTextItem {
  return { str, transform: [1, 0, 0, 1, x, y], width, height: 10 };
}

const page = (n: number, items: PdfTextItem[]): PdfPageText => ({ page: n, items });

describe("findTextHighlight", () => {
  it("finds an exact match inside one item", () => {
    const pages = [page(1, [item("Propagation of waves in media", 10, 700, 180)])];
    const match = findTextHighlight(pages, "waves");
    expect(match).not.toBeNull();
    expect(match!.page).toBe(1);
    expect(match!.rects.length).toBe(1);
    const rect = match!.rects[0];
    expect(rect.x0).toBe(10);
    expect(rect.y0).toBe(690);
    expect(rect.y1).toBe(700);
    expect(rect.x1).toBeGreaterThan(rect.x0);
  });

  it("rejoins words split across items", () => {
    const pages = [
      page(1, [
        item("Propagation of", 10, 700, 90),
        item("waves in", 100, 700, 60),
        item("piezothermoelastic media", 160, 700, 140),
      ]),
    ];
    const match = findTextHighlight(pages, "waves in piezothermoelastic");
    expect(match).not.toBeNull();
    expect(match!.page).toBe(1);
    // Two items overlap the match: the fully-covered middle item and the
    // partial third item.
    expect(match!.rects.length).toBe(2);
    expect(match!.rects[0].x0).toBe(100);
    expect(match!.rects[0].x1).toBe(160);
    expect(match!.rects[1].x0).toBe(160);
    expect(match!.rects[1].x1).toBeLessThan(300);
  });

  it("is case- and whitespace-insensitive", () => {
    const pages = [page(1, [item("  Propagation   OF WAVES ", 10, 700, 200)])];
    const match = findTextHighlight(pages, "propagation of waves");
    expect(match).not.toBeNull();
  });

  it("returns the first matching page", () => {
    const pages = [
      page(1, [item("introduction only", 10, 700, 120)]),
      page(2, [item("waves appear here", 10, 700, 120)]),
    ];
    const match = findTextHighlight(pages, "waves");
    expect(match!.page).toBe(2);
  });

  it("returns null for a missing or empty needle", () => {
    const pages = [page(1, [item("waves", 10, 700, 40)])];
    expect(findTextHighlight(pages, "quantum")).toBeNull();
    expect(findTextHighlight(pages, "")).toBeNull();
    expect(findTextHighlight([], "waves")).toBeNull();
  });
});

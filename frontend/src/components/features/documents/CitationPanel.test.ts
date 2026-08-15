/** Citation workspace tests (Sprint M10). */
import { describe, expect, it } from "vitest";
import {
  formatCitation,
  formatPageReference,
  formatParagraphReference,
} from "@/components/features/documents/CitationPanel";

const doc = {
  id: "obj:document:1",
  title: "Waves in Media",
  file_name: "waves.pdf",
  document_type: "pdf",
  created_at: "2026-08-07T00:00:00+00:00",
} as never;

describe("citation formatting", () => {
  it("formats an MLA-style citation with the year", () => {
    expect(formatCitation(doc)).toContain("Waves in Media");
    expect(formatCitation(doc)).toContain("PDF");
    expect(formatCitation(doc)).toContain("2026");
    expect(formatCitation(doc)).toContain("AcademicOS");
  });

  it("formats page references", () => {
    expect(formatPageReference(3)).toBe("p. 3");
  });

  it("formats paragraph references from a selection", () => {
    expect(formatParagraphReference(2, "  waves  propagate  ")).toContain("p. 2");
    expect(formatParagraphReference(2, "waves propagate")).toContain("waves propagate");
    expect(formatParagraphReference(2, "")).toBe("p. 2");
  });
});

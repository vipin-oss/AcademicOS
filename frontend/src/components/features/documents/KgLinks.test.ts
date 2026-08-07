/** Knowledge-graph link extraction tests (Sprint M10). */
import { describe, expect, it } from "vitest";
import { extractObjectReferences } from "@/components/features/documents/KgLinks";

describe("extractObjectReferences", () => {
  it("extracts linked AcademicOS objects from metadata", () => {
    const refs = extractObjectReferences({
      "related.faculty": "obj:faculty:ABC",
      "related.project": "obj:project:XYZ",
      "doc.author": "obj:faculty:DEF",
      "plain.title": "not an object",
    });
    expect(refs).toContainEqual({ label: "Faculty", objectId: "obj:faculty:ABC" });
    expect(refs).toContainEqual({ label: "Project", objectId: "obj:project:XYZ" });
    expect(refs).toContainEqual({ label: "Faculty", objectId: "obj:faculty:DEF" });
    expect(refs.some((r) => r.objectId === "not an object")).toBe(false);
  });

  it("returns [] when no object references exist", () => {
    expect(extractObjectReferences({})).toEqual([]);
  });

  it("handles array-valued metadata", () => {
    const refs = extractObjectReferences({ "related.events": ["obj:event:1", "obj:event:2"] });
    expect(refs).toHaveLength(2);
    expect(refs.every((r) => r.label === "Event")).toBe(true);
  });
});

/** Office text extraction tests (Sprint M10, final polish). */
import JSZip from "jszip";
import { describe, expect, it } from "vitest";
import { extractOfficeText } from "@/lib/documents/officeText";

async function zipBlob(files: Record<string, string>): Promise<Blob> {
  const zip = new JSZip();
  for (const [name, content] of Object.entries(files)) {
    zip.file(name, content);
  }
  return zip.generateAsync({ type: "blob" });
}

describe("extractOfficeText", () => {
  it("extracts docx paragraph text", async () => {
    const blob = await zipBlob({
      "word/document.xml":
        "<w:document><w:body><w:p><w:r><w:t>Wave propagation in piezothermoelastic media</w:t></w:r></w:p></w:body></w:document>",
    });
    const text = await extractOfficeText(blob, "docx");
    expect(text).toContain("Wave propagation");
  });

  it("extracts pptx slide text in order", async () => {
    const blob = await zipBlob({
      "ppt/slides/slide2.xml": "<p:sp><p:txBody><a:p><a:r><a:t>Second slide</a:t></a:r></a:p></p:txBody></p:sp>",
      "ppt/slides/slide1.xml": "<p:sp><p:txBody><a:p><a:r><a:t>First slide</a:t></a:r></a:p></p:txBody></p:sp>",
    });
    const text = await extractOfficeText(blob, "pptx");
    expect(text).not.toBeNull();
    expect(text!.indexOf("First slide")).toBeLessThan(text!.indexOf("Second slide"));
  });

  it("extracts xlsx shared-string cells", async () => {
    const blob = await zipBlob({
      "xl/sharedStrings.xml":
        "<sst><si><t>Waves</t></si><si><t>Media</t></si></sst>",
      "xl/worksheets/sheet1.xml":
        '<worksheet><sheetData><row><c t="s"><v>0</v></c><c t="s"><v>1</v></c></row></sheetData></worksheet>',
    });
    const text = await extractOfficeText(blob, "xlsx");
    expect(text).toContain("Waves");
    expect(text).toContain("Media");
  });

  it("returns null for unreadable packages", async () => {
    const blob = new Blob(["not a zip"], { type: "application/octet-stream" });
    expect(await extractOfficeText(blob, "docx")).toBeNull();
  });

  it("returns null when required parts are missing", async () => {
    const blob = await zipBlob({ "random.txt": "hello" });
    expect(await extractOfficeText(blob, "docx")).toBeNull();
  });
});

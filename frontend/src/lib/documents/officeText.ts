/**
 * Office document text extraction (Sprint M10, final polish).
 *
 * DOCX / PPTX / XLSX are ZIP packages; this module extracts a readable
 * text approximation from their XML parts with JSZip — no fake content,
 * honest fallback when the package is unreadable.
 */

import JSZip from "jszip";

const stripXml = (xml: string): string =>
  xml
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/\s+/g, " ")
    .trim();

/** Blob -> ArrayBuffer (FileReader is available in browsers AND jsdom,
 * unlike Blob.arrayBuffer). */
function blobToArrayBuffer(blob: Blob): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(reader.error ?? new Error("read failed"));
    reader.readAsArrayBuffer(blob);
  });
}

/** Best-effort readable text from an office package; null when impossible. */
export async function extractOfficeText(
  blob: Blob,
  documentType: "docx" | "pptx" | "xlsx",
): Promise<string | null> {
  try {
    const zip = await JSZip.loadAsync(await blobToArrayBuffer(blob));
    if (documentType === "docx") {
      const entry = zip.file("word/document.xml");
      if (!entry) return null;
      return stripXml(await entry.async("text"));
    }
    if (documentType === "pptx") {
      const slides = Object.keys(zip.files)
        .filter((name) => /^ppt\/slides\/slide\d+\.xml$/.test(name))
        .sort((a, b) => {
          const na = Number(a.match(/slide(\d+)\.xml/)?.[1] ?? 0);
          const nb = Number(b.match(/slide(\d+)\.xml/)?.[1] ?? 0);
          return na - nb;
        });
      if (slides.length === 0) return null;
      const parts: string[] = [];
      for (const slide of slides) {
        const text = stripXml(await zip.file(slide)!.async("text"));
        parts.push(`--- Slide ${slides.indexOf(slide) + 1} ---\n${text}`);
      }
      return parts.join("\n\n");
    }
    if (documentType === "xlsx") {
      const shared = zip.file("xl/sharedStrings.xml");
      const sheet = zip.file("xl/worksheets/sheet1.xml");
      if (!shared && !sheet) return null;
      const strings = shared
        ? stripXml(await shared.async("text")).split(" ")
        : [];
      const sheetXml = sheet ? await sheet.async("text") : "";
      // Extract cell values (t="s" shared refs, t="str"/inline text).
      const cells: string[] = [];
      const cellRe = /<c\b([^>]*)>([\s\S]*?)<\/c>/g;
      let cellMatch: RegExpExecArray | null;
      while ((cellMatch = cellRe.exec(sheetXml)) !== null) {
        const typeMatch = cellMatch[1].match(/\bt="(\w+)"/);
        const type = typeMatch ? typeMatch[1] : "";
        const vMatch = cellMatch[2].match(/<v>([^<]*)<\/v>/);
        const isMatch = cellMatch[2].match(/<is><t>([^<]*)<\/t><\/is>/);
        const value = isMatch ? isMatch[1] : vMatch ? vMatch[1] : "";
        if (type === "s") {
          cells.push(strings[Number(value)] ?? "");
        } else if (value) {
          cells.push(value);
        }
      }
      const rows: string[] = [];
      for (let i = 0; i < cells.length; i += 8) {
        rows.push(cells.slice(i, i + 8).join("\t"));
      }
      return rows.join("\n") || null;
    }
    return null;
  } catch {
    return null;
  }
}

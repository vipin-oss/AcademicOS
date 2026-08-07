import type { DocumentStatus, DocumentTypeValue } from "@/types";

/** Every document type the UI knows how to render an icon/badge for. */
export const DOCUMENT_TYPES: DocumentTypeValue[] = [
  "pdf",
  "docx",
  "xlsx",
  "pptx",
  "txt",
  "zip",
  "image",
  "video",
  "unknown",
];

export const DOCUMENT_STATUSES: DocumentStatus[] = ["draft", "active", "archived"];

/** Rows per page on the Documents list. */
export const DEFAULT_DOC_PAGE_SIZE = 12;

/**
 * The backend has no `q` / `type` / `status` parameters yet, so the list
 * filters client-side over a single "window" of documents. 100 = the backend's
 * `page_size` ceiling (mirrors the Objects module).
 */
export const SEARCH_WINDOW_SIZE = 100;

/**
 * Upload cap mirrored from the backend (`MAX_FILE_BYTES` in
 * `backend/app/application/dtos/intake.py`): reject the transfer
 * client-side instead of uploading a file the API will refuse.
 */
export const MAX_UPLOAD_BYTES = 512 * 1024 * 1024;

const EXTENSION_MAP: Record<string, DocumentTypeValue> = {
  pdf: "pdf",
  doc: "docx",
  docx: "docx",
  xls: "xlsx",
  xlsx: "xlsx",
  ppt: "pptx",
  pptx: "pptx",
  txt: "txt",
  md: "txt",
  csv: "txt",
  zip: "zip",
  "7z": "zip",
  rar: "zip",
  gz: "zip",
  png: "image",
  jpg: "image",
  jpeg: "image",
  gif: "image",
  webp: "image",
  svg: "image",
  bmp: "image",
  mp4: "video",
  mov: "video",
  webm: "video",
  avi: "video",
  mkv: "video",
};

/** Infer a {@link DocumentTypeValue} from a file name / extension. */
export function documentTypeFromFileName(fileName: string): DocumentTypeValue {
  const ext = fileName.includes(".")
    ? fileName.split(".").pop()?.toLowerCase() ?? ""
    : "";
  return EXTENSION_MAP[ext] ?? "unknown";
}

/** Infer a {@link DocumentTypeValue} from a MIME type, falling back to name. */
export function documentTypeFromMime(
  mime: string,
  fileName = "",
): DocumentTypeValue {
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("video/")) return "video";
  if (mime === "application/pdf" || mime === "application/x-pdf") return "pdf";
  if (
    mime.includes("spreadsheet") ||
    mime.includes("excel") ||
    mime === "application/vnd.ms-excel"
  )
    return "xlsx";
  if (
    mime.includes("presentation") ||
    mime.includes("powerpoint")
  )
    return "pptx";
  if (mime.includes("word") || mime === "application/msword") return "docx";
  if (mime.includes("zip") || mime.includes("compressed")) return "zip";
  return documentTypeFromFileName(fileName);
}

/** Human-readable file size: `1.2 MB`, `340 KB`, `812 B`. */
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(
    units.length - 1,
    Math.floor(Math.log(bytes) / Math.log(1024)),
  );
  const value = bytes / 1024 ** exponent;
  const rounded = exponent === 0 ? value : Math.round(value * 10) / 10;
  return `${rounded} ${units[exponent]}`;
}

import {
  FileArchive,
  FileImage,
  FileQuestion,
  FileSpreadsheet,
  FileText,
  FileVideo,
  Presentation,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { DocumentTypeValue } from "@/types";

const ICONS: Record<DocumentTypeValue, LucideIcon> = {
  pdf: FileText,
  docx: FileText,
  xlsx: FileSpreadsheet,
  pptx: Presentation,
  txt: FileText,
  zip: FileArchive,
  image: FileImage,
  video: FileVideo,
  unknown: FileQuestion,
};

const COLORS: Record<DocumentTypeValue, string> = {
  pdf: "text-[var(--danger)] bg-[var(--danger-subtle)]",
  docx: "text-[var(--info)] bg-[var(--info-subtle)]",
  xlsx: "text-[var(--success)] bg-[var(--success-subtle)]",
  pptx: "text-[var(--warning)] bg-[var(--warning-subtle)]",
  txt: "text-[var(--text-secondary)] bg-[var(--bg-hover)]",
  zip: "text-[var(--accent)] bg-[var(--accent-subtle)]",
  image: "text-[var(--info)] bg-[var(--info-subtle)]",
  video: "text-[var(--danger)] bg-[var(--danger-subtle)]",
  unknown: "text-[var(--text-tertiary)] bg-[var(--bg-hover)]",
};

/** Square, colour-coded file glyph for a given document type. */
export function FileIcon({
  type,
  className,
}: {
  type: DocumentTypeValue;
  className?: string;
}) {
  const Icon = ICONS[type] ?? FileQuestion;
  return (
    <span
      className={cn(
        "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
        COLORS[type] ?? COLORS.unknown,
        className,
      )}
      aria-hidden="true"
    >
      <Icon className="h-5 w-5" />
    </span>
  );
}

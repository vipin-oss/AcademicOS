"use client";

/**
 * Simple drag-and-drop upload component with automatic document analysis.
 * Shows a progress stepper: Upload → Processing → Done
 *
 * Analysis happens ONCE during upload (POST /documents).
 * No redundant second analysis call.
 */

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { Upload, CheckCircle2, Loader2, ExternalLink, FileText, AlertTriangle, Calendar, BookOpen, FlaskConical } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { uploadDocument, type UploadProgress } from "@/lib/api/documents";
import { cn } from "@/lib/utils";

interface UploadResult {
  id: string;
  title: string;
  document_type: string;
  file_name: string;
  duplicate_warning?: string | null;
  analysis?: {
    document_type_id?: string | null;
    confidence?: number;
    fields_count?: number;
    routing?: Array<{
      module: string;
      kind: string;
      object_id?: string;
      existing_id?: string;
      reason?: string;
    }>;
  } | null;
}

type Step = "upload" | "processing" | "done";

function StepIndicator({ step }: { step: Step }) {
  const steps = [
    { key: "upload", label: "Upload", icon: Upload },
    { key: "processing", label: "Process", icon: Loader2 },
    { key: "done", label: "Done", icon: CheckCircle2 },
  ];
  const activeIndex = steps.findIndex((s) => s.key === step);

  return (
    <div className="flex items-center gap-2">
      {steps.map((s, i) => {
        const Icon = s.icon;
        const active = i === activeIndex;
        const done = i < activeIndex;
        return (
          <div key={s.key} className="flex items-center gap-1.5">
            {i > 0 && <div className={cn("h-px w-6", done ? "bg-emerald-400" : "bg-[var(--border-subtle)]")} />}
            <div className={cn(
              "flex h-6 w-6 items-center justify-center rounded-full",
              done ? "bg-emerald-100 text-emerald-600" : active ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "bg-[var(--bg-hover)] text-[var(--text-tertiary)]"
            )}>
              {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : active ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
            </div>
            <span className={cn("text-xs", active ? "font-medium text-[var(--text-primary)]" : done ? "text-emerald-600" : "text-[var(--text-tertiary)]")}>
              {s.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function RoutingOutcome({ routing }: { routing: UploadResult["analysis"] }) {
  if (!routing?.routing || routing.routing.length === 0) return null;

  const created = routing.routing.filter((r) => r.kind === "created");
  const duplicates = routing.routing.filter((r) => r.kind === "duplicate");

  return (
    <div className="space-y-2">
      {created.map((r) => (
        <div key={r.object_id || r.module} className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <span className="text-sm font-semibold text-emerald-900">
              {r.module === "event" ? "Conference recorded" :
               r.module === "publication" ? "Publication recorded" :
               r.module === "project" ? "Research project recorded" :
               "Record created"}
            </span>
          </div>
          {r.object_id && (
            <Link
              href={r.module === "event" ? `/events/${r.object_id}` :
                    r.module === "publication" ? `/publications/${r.object_id}` :
                    r.module === "project" ? `/research/projects/${r.object_id}` :
                    `/objects/${r.object_id}`}
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:text-emerald-900 hover:underline"
            >
              View {r.module === "event" ? "Event" : "Record"} →
            </Link>
          )}
        </div>
      ))}

      {duplicates.map((r) => (
        <div key={r.existing_id || r.module} className="rounded-lg border border-blue-200 bg-blue-50 p-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-semibold text-blue-900">
              {r.module === "event" ? "Certificate linked to existing conference" :
               r.module === "publication" ? "Certificate linked to existing publication" :
               "Linked to existing record"}
            </span>
          </div>
          <p className="mt-1 text-xs text-blue-700">
            This certificate matches an existing {r.module === "event" ? "conference" : "record"}, so AcademicOS linked it instead of creating a duplicate.
          </p>
          {r.existing_id && (
            <Link
              href={r.module === "event" ? `/events/${r.existing_id}` :
                    r.module === "publication" ? `/publications/${r.existing_id}` :
                    r.module === "project" ? `/research/projects/${r.existing_id}` :
                    `/objects/${r.existing_id}`}
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-blue-700 hover:text-blue-900 hover:underline"
            >
              View {r.module === "event" ? "Event" : "Record"} →
            </Link>
          )}
        </div>
      ))}
    </div>
  );
}

export function SimpleUpload({ onUploaded }: { onUploaded?: (result: UploadResult) => void }) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const step: Step = uploading ? "processing" : result ? "done" : "upload";

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const file = files[0];
      if (!file) return;
      setUploading(true); setError(null); setResult(null); setProgress(0);
      try {
        const saved = await uploadDocument({ file }, { onProgress: (v: UploadProgress) => setProgress(v.percent) });
        const uploadResult: UploadResult = {
          id: saved.id,
          title: saved.title,
          document_type: saved.document_type,
          file_name: saved.file_name,
          duplicate_warning: (saved as any).duplicate_warning,
          analysis: (saved as any).analysis,
        };
        setResult(uploadResult);
        onUploaded?.(uploadResult);
      } catch (err) { setError(toErrorMessage(err, "Upload failed. Please try again.")); }
      finally { setUploading(false); setProgress(null); }
    },
    [onUploaded],
  );

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    if (e.dataTransfer.files.length > 0) void handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  return (
    <div className="space-y-3">
      {/* Progress stepper */}
      {(uploading || result) && (
        <div className="flex justify-center py-2">
          <StepIndicator step={step} />
        </div>
      )}

      {/* Upload zone */}
      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDragging(false); }}
        onClick={() => !uploading && inputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); !uploading && inputRef.current?.click(); }}}
        role="button" tabIndex={0} aria-label="Upload document"
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 transition-colors",
          dragging ? "border-[var(--accent)] bg-[var(--accent-subtle)]" : "border-[var(--border-strong)] hover:border-[var(--accent)] hover:bg-[var(--bg-hover)]",
          uploading && "pointer-events-none opacity-60",
        )}
      >
        {uploading ? (
          <>
            <Loader2 className="h-8 w-8 animate-spin text-[var(--accent)]" />
            <p className="text-sm font-medium text-[var(--text-primary)]">Uploading &amp; analyzing{progress !== null ? ` (${progress}%)` : "..."}</p>
          </>
        ) : result ? (
          <>
            <FileText className="h-8 w-8 text-emerald-500" />
            <p className="text-sm font-medium text-[var(--text-primary)]">Drop another file or click to browse</p>
          </>
        ) : (
          <>
            <Upload className="h-8 w-8 text-[var(--text-tertiary)]" />
            <div className="text-center">
              <p className="text-sm font-medium text-[var(--text-primary)]">Drop files here or click to browse</p>
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">PDF, DOCX, PPTX, XLSX, images, certificates, notices...</p>
            </div>
          </>
        )}
        <input ref={inputRef} type="file" onChange={(e) => e.target.files && e.target.files.length > 0 && void handleFiles(e.target.files)} disabled={uploading} className="sr-only" aria-label="Choose file" />
      </div>

      {/* Upload progress bar */}
      {uploading && progress !== null && (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]">
          <div className="h-full rounded-full bg-[var(--accent)] transition-all" style={{ width: `${progress}%` }} />
        </div>
      )}

      {/* Routing outcome from upload analysis */}
      {result?.analysis?.routing && result.analysis.routing.length > 0 && (
        <RoutingOutcome routing={result.analysis} />
      )}

      {/* Analysis summary (when no routing — generic document) */}
      {result?.analysis && (!result.analysis.routing || result.analysis.routing.length === 0) && (result.analysis.fields_count ?? 0) > 0 && (
        <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3">
          <p className="text-sm text-[var(--text-secondary)]">
            AcademicOS found <span className="font-medium text-[var(--text-primary)]">{result.analysis.fields_count}</span> pieces of information.
            {result.analysis.document_type_id && (
              <span> Document type: <span className="font-medium capitalize">{result.analysis.document_type_id.replace(/_/g, " ")}</span></span>
            )}
          </p>
          <Link href={`/documents/${result.id}`} className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:underline">
            <ExternalLink className="h-3 w-3" /> Review &amp; confirm
          </Link>
        </div>
      )}

      {/* Duplicate warning */}
      {result?.duplicate_warning && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-800">Similar document already exists</p>
              <p className="text-xs text-amber-700 mt-1">{result.duplicate_warning}</p>
            </div>
          </div>
        </div>
      )}

      {error && (
        <p className="rounded-lg border border-[var(--danger-subtle)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">{error}</p>
      )}
    </div>
  );
}

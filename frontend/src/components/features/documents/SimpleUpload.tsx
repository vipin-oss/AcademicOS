"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { Upload, CheckCircle2, Loader2, ExternalLink } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { uploadDocument, type UploadProgress } from "@/lib/api/documents";
import { analyzeDocument, type DocumentAnalysisResponse } from "@/lib/api/documentIntake";
import { DocumentAnalysisResult } from "./DocumentAnalysisResult";
import { cn } from "@/lib/utils";

interface UploadResult {
  id: string;
  title: string;
  document_type: string;
  file_name: string;
}

/**
 * Simple drag-and-drop upload component with automatic document analysis.
 * Uploads file, then runs intelligence analysis showing confidence, extracted
 * fields, detected records, and any conflicts requiring review.
 */
export function SimpleUpload({ onUploaded }: { onUploaded?: (result: UploadResult) => void }) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [analysis, setAnalysis] = useState<DocumentAnalysisResponse | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const runAnalysis = useCallback(async (docId: string) => {
    setAnalyzing(true);
    try {
      const analysisResult = await analyzeDocument(docId);
      setAnalysis(analysisResult);
    } catch {
      setAnalysis(null);
    } finally {
      setAnalyzing(false);
    }
  }, []);

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const file = files[0];
      if (!file) return;

      setUploading(true);
      setError(null);
      setResult(null);
      setAnalysis(null);
      setProgress(0);

      try {
        const saved = await uploadDocument(
          { file },
          { onProgress: (value: UploadProgress) => setProgress(value.percent) },
        );
        const uploadResult: UploadResult = {
          id: saved.id,
          title: saved.title,
          document_type: saved.document_type,
          file_name: saved.file_name,
        };
        setResult(uploadResult);
        onUploaded?.(uploadResult);

        // Run document analysis
        await runAnalysis(saved.id);
      } catch (err) {
        setError(toErrorMessage(err, "Upload failed. Please try again."));
      } finally {
        setUploading(false);
        setProgress(null);
      }
    },
    [onUploaded, runAnalysis],
  );

  const handleRetry = useCallback(() => {
    if (result?.id) {
      void runAnalysis(result.id);
    }
  }, [result?.id, runAnalysis]);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (e.dataTransfer.files.length > 0) void handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  return (
    <div className="space-y-3">
      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDragging(false); }}
        onClick={() => !uploading && inputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); !uploading && inputRef.current?.click(); }}}
        role="button"
        tabIndex={0}
        aria-label="Upload document"
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 transition-colors",
          dragging ? "border-[var(--accent)] bg-[var(--accent-subtle)]" : "border-[var(--border-strong)] hover:border-[var(--accent)] hover:bg-[var(--bg-hover)]",
          uploading && "pointer-events-none opacity-60",
        )}
      >
        {uploading ? (
          <>
            <Loader2 className="h-8 w-8 animate-spin text-[var(--accent)]" />
            <p className="text-sm font-medium text-[var(--text-primary)]">Uploading{progress !== null ? ` (${progress}%)` : "..."}</p>
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

      {uploading && progress !== null && (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]">
          <div className="h-full rounded-full bg-[var(--accent)] transition-all" style={{ width: `${progress}%` }} />
        </div>
      )}

      {/* Upload success with link */}
      {result && !analysis && !analyzing && (
        <div className="flex items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-emerald-900">{result.title}</p>
            <p className="text-xs text-emerald-700">{result.document_type.toUpperCase()} · {result.file_name}</p>
          </div>
          <Link
            href={`/documents/${result.id}`}
            className="inline-flex items-center gap-1 rounded-lg bg-emerald-100 px-2.5 py-1.5 text-xs font-medium text-emerald-800 hover:bg-emerald-200"
          >
            <ExternalLink className="h-3 w-3" /> View
          </Link>
        </div>
      )}

      {/* Document analysis result with enrichment status */}
      {(analysis || analyzing) && (
        <div className="space-y-2">
          <DocumentAnalysisResult
            analysis={analysis}
            analyzing={analyzing}
            fileName={result?.file_name}
            onRetryEnrichment={handleRetry}
          />
          {result && analysis && (
            <Link
              href={`/documents/${result.id}`}
              className="inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:underline"
            >
              <ExternalLink className="h-3 w-3" /> View document details
            </Link>
          )}
        </div>
      )}

      {error && (
        <p className="rounded-lg border border-[var(--danger-subtle)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">{error}</p>
      )}
    </div>
  );
}

"use client";

/**
 * Multi-file upload component for academic documents.
 *
 * Each file gets its own independent lifecycle:
 * queued → uploading → analyzing → completed / failed / requires review
 *
 * One file's failure does NOT affect others.
 * Uses existing uploadDocument and analyzeDocument APIs.
 * Bounded concurrency: max 3 files processed simultaneously.
 */

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import {
  Upload,
  CheckCircle2,
  Loader2,
  XCircle,
  AlertCircle,
  ExternalLink,
  X,
  FileText,
  RefreshCw,
} from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { uploadDocument, type UploadProgress } from "@/lib/api/documents";
import {
  analyzeDocument,
  type DocumentAnalysisResponse,
} from "@/lib/api/documentIntake";
import { DocumentAnalysisResult } from "./DocumentAnalysisResult";
import { cn } from "@/lib/utils";
import { formatFileSize } from "@/lib/documents/constants";

// --- Types ---

type FileStatus =
  | "queued"
  | "uploading"
  | "uploaded"
  | "analyzing"
  | "completed"
  | "failed"
  | "requires_review";

interface FileItem {
  id: string; // local unique id
  file: File;
  status: FileStatus;
  progress: number;
  documentId?: string;
  title?: string;
  documentType?: string;
  analysis?: DocumentAnalysisResponse;
  error?: string;
}

interface BatchSummary {
  total: number;
  completed: number;
  needsReview: number;
  failed: number;
}

// --- Constants ---

const MAX_CONCURRENT = 3;
const STATUS_LABELS: Record<FileStatus, string> = {
  queued: "Queued",
  uploading: "Uploading",
  uploaded: "Uploaded",
  analyzing: "Understanding",
  completed: "Completed",
  failed: "Could not process",
  requires_review: "Needs review",
};

// --- Component ---

export function MultiFileUpload({
  onBatchComplete,
}: {
  onBatchComplete?: (summary: BatchSummary) => void;
} = {}) {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const [processing, setProcessing] = useState(false);
  const activeCount = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // --- File selection ---

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const items: FileItem[] = Array.from(newFiles).map((file) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      file,
      status: "queued",
      progress: 0,
    }));
    setFiles((prev) => [...prev, ...items]);
  }, []);

  const removeFile = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setFiles([]);
    setProcessing(false);
  }, []);

  // --- Single file lifecycle ---

  const processFile = useCallback(async (item: FileItem) => {
    // Phase 1: Upload
    setFiles((prev) =>
      prev.map((f) =>
        f.id === item.id ? { ...f, status: "uploading" as const, progress: 0 } : f
      )
    );

    try {
      const saved = await uploadDocument(
        { file: item.file },
        {
          onProgress: (p: UploadProgress) => {
            setFiles((prev) =>
              prev.map((f) =>
                f.id === item.id ? { ...f, progress: p.percent } : f
              )
            );
          },
        }
      );

      setFiles((prev) =>
        prev.map((f) =>
          f.id === item.id
            ? {
                ...f,
                status: "uploaded" as const,
                documentId: saved.id,
                title: saved.title,
                documentType: saved.document_type,
                progress: 100,
              }
            : f
        )
      );

      // Phase 2: Analysis
      setFiles((prev) =>
        prev.map((f) =>
          f.id === item.id ? { ...f, status: "analyzing" as const } : f
        )
      );

      try {
        const analysis = await analyzeDocument(saved.id);
        const needsReview =
          analysis.review_required ||
          (analysis.conflicts && analysis.conflicts.length > 0);

        setFiles((prev) =>
          prev.map((f) =>
            f.id === item.id
              ? {
                  ...f,
                  status: needsReview ? "requires_review" : "completed",
                  analysis,
                }
              : f
          )
        );
      } catch {
        // Analysis failed but upload succeeded — mark as completed (deterministic only)
        setFiles((prev) =>
          prev.map((f) =>
            f.id === item.id
              ? { ...f, status: "completed" as const }
              : f
          )
        );
      }
    } catch (err) {
      setFiles((prev) =>
        prev.map((f) =>
          f.id === item.id
            ? {
                ...f,
                status: "failed" as const,
                error: toErrorMessage(err, "Upload failed"),
              }
            : f
        )
      );
    }
  }, []);

  // --- Batch processing with bounded concurrency ---

  const startUpload = useCallback(async () => {
    const queued = files.filter((f) => f.status === "queued");
    if (queued.length === 0) return;

    setProcessing(true);
    activeCount.current = 0;

    const queue = [...queued];
    const workers: Promise<void>[] = [];

    const runNext = async (): Promise<void> => {
      const next = queue.shift();
      if (!next) return;
      activeCount.current++;
      await processFile(next);
      activeCount.current--;
      await runNext();
    };

    // Start bounded concurrent workers
    const concurrency = Math.min(MAX_CONCURRENT, queue.length);
    for (let i = 0; i < concurrency; i++) {
      workers.push(runNext());
    }

    await Promise.all(workers);
    setProcessing(false);

    // Report summary
    setFiles((current) => {
      const summary: BatchSummary = {
        total: current.length,
        completed: current.filter(
          (f) => f.status === "completed" || f.status === "requires_review"
        ).length,
        needsReview: current.filter((f) => f.status === "requires_review").length,
        failed: current.filter((f) => f.status === "failed").length,
      };
      onBatchComplete?.(summary);
      return current;
    });
  }, [files, processFile, onBatchComplete]);

  // --- Retry single file ---

  const retryFile = useCallback(
    async (id: string) => {
      const item = files.find((f) => f.id === id);
      if (!item || item.status !== "failed") return;
      setFiles((prev) =>
        prev.map((f) =>
          f.id === id ? { ...f, status: "queued" as const, error: undefined } : f
        )
      );
      // Process immediately
      await processFile({ ...item, status: "queued", error: undefined });
    },
    [files, processFile]
  );

  // --- Drop handlers ---

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (e.dataTransfer.files.length > 0) addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  // --- Computed state ---

  const queuedCount = files.filter((f) => f.status === "queued").length;
  const hasFiles = files.length > 0;
  const isProcessing = processing;
  const allDone =
    files.length > 0 && files.every((f) =>
      ["completed", "failed", "requires_review"].includes(f.status)
    );

  const summary: BatchSummary = {
    total: files.length,
    completed: files.filter((f) => f.status === "completed").length,
    needsReview: files.filter((f) => f.status === "requires_review").length,
    failed: files.filter((f) => f.status === "failed").length,
  };

  // --- Render ---

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDrop={onDrop}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragging(false);
        }}
        onClick={() => !isProcessing && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            !isProcessing && inputRef.current?.click();
          }
        }}
        role="button"
        tabIndex={0}
        aria-label="Upload documents"
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 transition-colors",
          dragging
            ? "border-[var(--accent)] bg-[var(--accent-subtle)]"
            : "border-[var(--border-strong)] hover:border-[var(--accent)] hover:bg-[var(--bg-hover)]",
          isProcessing && "pointer-events-none opacity-60"
        )}
      >
        <Upload className="h-8 w-8 text-[var(--text-tertiary)]" />
        <div className="text-center">
          <p className="text-sm font-medium text-[var(--text-primary)]">
            Drop files here or click to browse
          </p>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">
            Select multiple files — PDF, DOCX, PPTX, XLSX, images, certificates...
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          onChange={(e) => e.target.files && addFiles(e.target.files)}
          disabled={isProcessing}
          className="sr-only"
          aria-label="Choose files"
        />
      </div>

      {/* File list */}
      {hasFiles && (
        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
          <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-4 py-3">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              {files.length} file{files.length !== 1 ? "s" : ""} selected
            </h3>
            <div className="flex items-center gap-2">
              {!isProcessing && !allDone && (
                <button
                  type="button"
                  onClick={() => void startUpload()}
                  className="rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--accent-hover)]"
                >
                  Upload All
                </button>
              )}
              {!isProcessing && (
                <button
                  type="button"
                  onClick={clearAll}
                  className="rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* File items */}
          <div className="divide-y divide-[var(--border-subtle)]">
            {files.map((item) => (
              <FileItemRow
                key={item.id}
                item={item}
                onRemove={() => removeFile(item.id)}
                onRetry={() => void retryFile(item.id)}
                isProcessing={isProcessing}
              />
            ))}
          </div>
        </div>
      )}

      {/* Batch summary */}
      {allDone && (
        <BatchSummaryCard summary={summary} onClear={clearAll} />
      )}
    </div>
  );
}

// --- File Item Row ---

function FileItemRow({
  item,
  onRemove,
  onRetry,
  isProcessing,
}: {
  item: FileItem;
  onRemove: () => void;
  onRetry: () => void;
  isProcessing: boolean;
}) {
  const isActive = ["uploading", "analyzing"].includes(item.status);
  const isDone = ["completed", "requires_review", "failed"].includes(item.status);

  return (
    <div className="flex items-center gap-3 px-4 py-3">
      {/* Status icon */}
      <div className="shrink-0">
        {item.status === "uploading" || item.status === "analyzing" ? (
          <Loader2 className="h-4 w-4 animate-spin text-[var(--accent)]" />
        ) : item.status === "completed" ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        ) : item.status === "requires_review" ? (
          <AlertCircle className="h-4 w-4 text-amber-600" />
        ) : item.status === "failed" ? (
          <XCircle className="h-4 w-4 text-[var(--danger)]" />
        ) : (
          <FileText className="h-4 w-4 text-[var(--text-tertiary)]" />
        )}
      </div>

      {/* File info */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-[var(--text-primary)]">
          {item.title ?? item.file.name}
        </p>
        <p className="text-xs text-[var(--text-tertiary)]">
          {formatFileSize(item.file.size)} · {STATUS_LABELS[item.status]}
          {item.error && <span className="text-[var(--danger)]"> · {item.error}</span>}
        </p>

        {/* Upload progress bar */}
        {item.status === "uploading" && (
          <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]">
            <div
              className="h-full rounded-full bg-[var(--accent)] transition-all"
              style={{ width: `${item.progress}%` }}
            />
          </div>
        )}

        {/* Analysis result preview */}
        {item.analysis && item.status === "requires_review" && (
          <div className="mt-1 text-xs text-amber-700">
            {item.analysis.conflicts && item.analysis.conflicts.length > 0
              ? `${item.analysis.conflicts.length} conflict(s) found`
              : "Some information needs review"}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex shrink-0 items-center gap-1">
        {item.documentId && isDone && (
          <Link
            href={`/documents/${item.documentId}`}
            className="rounded p-1 text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)]"
            title="View document"
          >
            <ExternalLink className="h-4 w-4" />
          </Link>
        )}
        {item.status === "failed" && (
          <button
            type="button"
            onClick={onRetry}
            className="rounded p-1 text-[var(--accent)] hover:bg-[var(--bg-hover)]"
            title="Retry"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        )}
        {!isProcessing && (
          <button
            type="button"
            onClick={onRemove}
            className="rounded p-1 text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)]"
            title="Remove"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}

// --- Batch Summary Card ---

function BatchSummaryCard({
  summary,
  onClear,
}: {
  summary: BatchSummary;
  onClear: () => void;
}) {
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
      <h3 className="mb-2 text-sm font-semibold text-[var(--text-primary)]">
        Upload Complete
      </h3>
      <div className="mb-3 space-y-1 text-sm text-[var(--text-secondary)]">
        <p>
          <span className="font-medium">{summary.total}</span> documents processed
        </p>
        {summary.completed > 0 && (
          <p className="text-emerald-700">
            ✓ {summary.completed} completed
          </p>
        )}
        {summary.needsReview > 0 && (
          <p className="text-amber-700">
            ⚠ {summary.needsReview} need{summary.needsReview === 1 ? "s" : ""} review
          </p>
        )}
        {summary.failed > 0 && (
          <p className="text-[var(--danger)]">
            ✗ {summary.failed} could not be processed
          </p>
        )}
      </div>
      <div className="flex gap-2">
        <Link
          href="/documents"
          className="rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--accent-hover)]"
        >
          View Documents
        </Link>
        <button
          type="button"
          onClick={onClear}
          className="rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
        >
          Upload More
        </button>
      </div>
    </div>
  );
}

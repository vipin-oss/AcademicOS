"use client";

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { useModalDismiss } from "@/hooks/useModalDismiss";
import { cn } from "@/lib/utils";
import { Spinner } from "./Spinner";

/**
 * Accessible confirmation dialog (replaces `window.confirm`).
 * Buttons are disabled while `loading` so the action cannot be fired twice.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  loadingLabel,
  tone = "danger",
  loading = false,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  loadingLabel?: string;
  tone?: "danger" | "accent";
  loading?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useModalDismiss({ open, onDismiss: onCancel, disabled: loading });

  useEffect(() => {
    if (open) confirmRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center bg-black/40 p-4 sm:items-center"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !loading) onCancel();
      }}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        className="w-full max-w-md rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 shadow-lg sm:p-6"
      >
        <div className="flex items-start gap-3">
          <div
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
              tone === "danger"
                ? "bg-[var(--danger-subtle)] text-[var(--danger)]"
                : "bg-[var(--accent-subtle)] text-[var(--accent)]",
            )}
          >
            <AlertTriangle className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0 flex-1">
            <h2
              id="confirm-dialog-title"
              className="text-base font-semibold text-[var(--text-primary)]"
            >
              {title}
            </h2>
            {description ? (
              <div className="mt-1 break-words text-sm text-[var(--text-secondary)]">
                {description}
              </div>
            ) : null}
          </div>
        </div>

        {error ? (
          <p
            role="alert"
            className="mt-4 rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
          >
            {error}
          </p>
        ) : null}

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={cn(
              "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors disabled:cursor-not-allowed disabled:opacity-60",
              tone === "danger"
                ? "bg-[var(--danger)] hover:opacity-90"
                : "bg-[var(--accent)] hover:bg-[var(--accent-hover)]",
            )}
          >
            {loading ? <Spinner /> : null}
            {loading ? loadingLabel ?? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

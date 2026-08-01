"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

export type ToastKind = "success" | "error" | "warning" | "info";

export interface ToastState {
  kind: ToastKind;
  message: string;
  /** ms before auto-dismiss; 0 keeps it until dismissed. */
  duration?: number;
}

const DEFAULT_DURATION: Record<ToastKind, number> = {
  success: 3500,
  info: 3500,
  warning: 6000,
  error: 6000,
};

const STYLES: Record<ToastKind, { icon: typeof CheckCircle2; className: string }> = {
  success: { icon: CheckCircle2, className: "text-[var(--success)]" },
  error: { icon: AlertCircle, className: "text-[var(--danger)]" },
  warning: { icon: AlertTriangle, className: "text-[var(--warning)]" },
  info: { icon: Info, className: "text-[var(--info)]" },
};

export function useToast() {
  const [toast, setToast] = useState<ToastState | null>(null);

  const show = useCallback((kind: ToastKind, message: string, duration?: number) => {
    setToast({ kind, message, duration });
  }, []);

  const dismiss = useCallback(() => setToast(null), []);

  return { toast, show, dismiss };
}

export function Toast({ toast, onClose }: { toast: ToastState | null; onClose: () => void }) {
  useEffect(() => {
    if (!toast) return;
    const duration = toast.duration ?? DEFAULT_DURATION[toast.kind];
    if (duration <= 0) return;
    const timer = setTimeout(onClose, duration);
    return () => clearTimeout(timer);
  }, [toast, onClose]);

  if (!toast) return null;

  const { icon: Icon, className } = STYLES[toast.kind];

  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-4 bottom-4 z-[70] flex justify-center sm:inset-x-auto sm:bottom-6 sm:right-6 sm:justify-end"
    >
      <div className="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-3 shadow-lg">
        <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", className)} aria-hidden="true" />
        <span className="flex-1 break-words text-sm text-[var(--text-primary)]">
          {toast.message}
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Dismiss notification"
          className="mt-0.5 shrink-0 rounded p-0.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

"use client";

/** Shared shell for the authentication pages: centred card on the app
 * background, no sidebar. */
import type { ReactNode } from "react";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--bg-app)] px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 flex items-center justify-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--accent)] text-xl text-white">
            🎓
          </div>
          <div>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">AcademicOS</h1>
            <p className="text-sm text-[var(--text-secondary)]">
              The Academic Operating System
            </p>
          </div>
        </div>
        <div className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 shadow-sm sm:p-8">
          {children}
        </div>
        <p className="mt-6 text-center text-xs text-[var(--text-tertiary)]">
          Local development release — data stays on this machine.
        </p>
      </div>
    </div>
  );
}

export function Field({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  autoComplete,
  required = true,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-[var(--text-primary)]">
        {label}
      </span>
      <input
        type={type}
        value={value}
        required={required}
        autoComplete={autoComplete}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none"
      />
    </label>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className="rounded-lg border border-[var(--danger-subtle)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
      {message}
    </p>
  );
}

export function SubmitButton({
  busy,
  children,
}: {
  busy: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="submit"
      disabled={busy}
      className="w-full rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60"
    >
      {busy ? "Please wait…" : children}
    </button>
  );
}

"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";

import { forgotPassword } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { AuthShell, Field, FormError, SubmitButton } from "@/components/features/auth/AuthShell";

export default function ForgotPasswordPage() {
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await forgotPassword(username);
      // This release has no email gateway: the reset token is returned in
      // the response body (local/dev transport).
      if (!result.reset_token) {
        setToken("");
      } else {
        setToken(result.reset_token);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Request failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      <h2 className="mb-6 text-lg font-semibold text-[var(--text-primary)]">Reset your password</h2>
      {token === null ? (
        <form onSubmit={onSubmit} className="space-y-4">
          <p className="text-sm text-[var(--text-secondary)]">
            Enter your username and we will issue a one-time reset token
            (returned here — this local release has no email gateway).
          </p>
          <Field label="Username" value={username} onChange={setUsername} autoComplete="username" />
          <FormError message={error} />
          <SubmitButton busy={busy}>Get reset token</SubmitButton>
        </form>
      ) : token === "" ? (
        <div className="space-y-4">
          <p className="text-sm text-[var(--text-secondary)]">
            No account matches that username — nothing was issued.
          </p>
          <button
            type="button"
            onClick={() => setToken(null)}
            className="w-full rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--accent-hover)]"
          >
            Try again
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-[var(--text-secondary)]">
            Copy this one-time token (valid 30 minutes):
          </p>
          <code className="block break-all rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-xs text-[var(--text-primary)]">
            {token}
          </code>
          <Link
            href={`/reset-password?token=${encodeURIComponent(token)}`}
            className="block w-full rounded-lg bg-[var(--accent)] px-4 py-2 text-center text-sm font-semibold text-white hover:bg-[var(--accent-hover)]"
          >
            Continue to reset
          </Link>
        </div>
      )}
      <p className="mt-6 text-center text-sm text-[var(--text-secondary)]">
        <Link href="/login" className="text-[var(--accent)] hover:underline">
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}

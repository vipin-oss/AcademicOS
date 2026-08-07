"use client";

export const dynamic = "force-dynamic";

import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { resetPassword } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { AuthShell, Field, FormError, SubmitButton } from "@/components/features/auth/AuthShell";

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}

function ResetPasswordForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [token, setToken] = useState(params.get("token") ?? "");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reset failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <AuthShell>
        <h2 className="mb-6 text-lg font-semibold text-[var(--text-primary)]">Password updated</h2>
        <p className="mb-6 text-sm text-[var(--text-secondary)]">
          Your password has been changed. Sign in with the new password.
        </p>
        <Link
          href="/login"
          className="block w-full rounded-lg bg-[var(--accent)] px-4 py-2 text-center text-sm font-semibold text-white hover:bg-[var(--accent-hover)]"
        >
          Sign in
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <h2 className="mb-6 text-lg font-semibold text-[var(--text-primary)]">Choose a new password</h2>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Reset token" value={token} onChange={setToken} autoComplete="off" />
        <Field
          label="New password (min. 8 characters)"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
        />
        <Field
          label="Confirm new password"
          type="password"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
        />
        <FormError message={error} />
        <SubmitButton busy={busy}>Reset password</SubmitButton>
      </form>
      <p className="mt-6 text-center text-sm text-[var(--text-secondary)]">
        <Link href="/login" className="text-[var(--accent)] hover:underline">
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}

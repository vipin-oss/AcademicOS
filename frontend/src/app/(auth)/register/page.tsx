"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";

import { useAuth } from "@/lib/auth/session";
import { ApiError } from "@/lib/api/client";
import { AuthShell, Field, FormError, SubmitButton } from "@/components/features/auth/AuthShell";

export default function RegisterPage() {
  const { register } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await register(username, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      <h2 className="mb-6 text-lg font-semibold text-[var(--text-primary)]">Create your account</h2>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Username" value={username} onChange={setUsername} autoComplete="username" />
        <Field
          label="Password (min. 8 characters)"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
        />
        <Field
          label="Confirm password"
          type="password"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
        />
        <FormError message={error} />
        <SubmitButton busy={busy}>Create account</SubmitButton>
      </form>
      <p className="mt-6 text-center text-sm text-[var(--text-secondary)]">
        Already have an account?{" "}
        <Link href="/login" className="text-[var(--accent)] hover:underline">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}

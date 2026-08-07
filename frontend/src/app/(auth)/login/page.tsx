"use client";

export const dynamic = "force-dynamic";

import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/lib/auth/session";
import { ApiError } from "@/lib/api/client";
import { AuthShell, Field, FormError, SubmitButton } from "@/components/features/auth/AuthShell";

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      const next = params.get("next");
      router.replace(next && next.startsWith("/") ? next : "/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign in failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      <h2 className="mb-6 text-lg font-semibold text-[var(--text-primary)]">Sign in</h2>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Username" value={username} onChange={setUsername} autoComplete="username" />
        <Field
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
        />
        <FormError message={error} />
        <SubmitButton busy={busy}>Sign in</SubmitButton>
      </form>
      <div className="mt-6 flex items-center justify-between text-sm">
        <Link href="/register" className="text-[var(--accent)] hover:underline">
          Create an account
        </Link>
        <Link href="/forgot-password" className="text-[var(--text-secondary)] hover:underline">
          Forgot password?
        </Link>
      </div>
    </AuthShell>
  );
}

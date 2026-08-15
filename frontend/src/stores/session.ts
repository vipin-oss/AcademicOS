"use client";

/** Session store (final release).
 *
 * The canonical session implementation lives in `@/lib/auth/session`
 * (AuthProvider + useAuth). This module is the store-location facade the
 * UI convention expects (`src/stores/`): it re-exports the provider and
 * the hook so feature code can import the session from either location
 * without duplicating any logic.
 */
export { AuthProvider, useAuth } from "@/lib/auth/session";
export type { AuthStatus } from "@/lib/auth/session";

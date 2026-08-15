"use client";

/** Session management (final release): automatic login (token restore),
 * automatic logout (expired refresh), profile loading, and the auth-state
 * hook every guarded page consumes. */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";

import { getMe, login as apiLogin, register as apiRegister } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { clearTokens, getAccessToken, setTokens } from "@/lib/auth/token";
import type { AuthUser } from "@/types";

export type AuthStatus = "loading" | "authed" | "anon";

interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  /** Sign in; throws ApiError on invalid credentials. */
  login: (username: string, password: string) => Promise<void>;
  /** Create an account and sign in immediately. */
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  // Automatic login: restore the session from stored tokens.
  useEffect(() => {
    let cancelled = false;
    async function restore() {
      const access = getAccessToken();
      if (!access) {
        if (!cancelled) setStatus("anon");
        return;
      }
      try {
        const me = await getMe();
        if (!cancelled) {
          setUser(me);
          setStatus("authed");
        }
      } catch (error) {
        // The interceptor already attempted a silent refresh; if we still
        // land here the session is dead — sign out.
        if (!cancelled) {
          clearTokens();
          setUser(null);
          setStatus("anon");
        }
      }
    }
    void restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (username: string, password: string) => {
      const tokens = await apiLogin(username, password);
      setTokens(tokens.access_token, tokens.refresh_token);
      const me = await getMe();
      setUser(me);
      setStatus("authed");
      router.replace("/");
    },
    [router],
  );

  const register = useCallback(
    async (username: string, password: string) => {
      await apiRegister(username, password);
      await login(username, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    setStatus("anon");
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({ status, user, login, register, logout }),
    [status, user, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export { ApiError };

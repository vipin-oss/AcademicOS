const ACCESS_TOKEN_KEY = "academicos.access_token";
const REFRESH_TOKEN_KEY = "academicos.refresh_token";
const SESSION_COOKIE = "academicos.session";

/** Access + refresh tokens in Local Storage, plus a lightweight session
 * cookie mirror so Next.js middleware can redirect unauthenticated users
 * (middleware cannot read Local Storage). All three are cleared together. */

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  setSessionCookie();
}

export function clearTokens(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  clearSessionCookie();
}

function setSessionCookie(): void {
  document.cookie = `${SESSION_COOKIE}=1; path=/; SameSite=Lax`;
}

function clearSessionCookie(): void {
  document.cookie = `${SESSION_COOKIE}=; path=/; SameSite=Lax; Max-Age=0`;
}

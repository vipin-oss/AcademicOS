/** Auth API client — the complete frontend authentication surface. */
import { api, type RequestOptions } from "@/lib/api/client";
import type { AuthTokens, AuthUser } from "@/types";

/** `POST /auth/register` — create an account (201; 409 duplicate). */
export function register(
  username: string,
  password: string,
  options?: RequestOptions,
): Promise<AuthUser> {
  return api.post<AuthUser>("/auth/register", { username, password }, options);
}

/** `POST /auth/login` — verify credentials, returns the token pair. */
export function login(
  username: string,
  password: string,
  options?: RequestOptions,
): Promise<AuthTokens> {
  return api.post<AuthTokens>("/auth/login", { username, password }, options);
}

/** `POST /auth/refresh` — exchange a refresh token for a fresh pair. */
export function refresh(
  refreshToken: string,
  options?: RequestOptions,
): Promise<AuthTokens> {
  return api.post<AuthTokens>("/auth/refresh", { refresh_token: refreshToken }, options);
}

/** `GET /auth/me` — the authenticated user (roles included). */
export function getMe(options?: RequestOptions): Promise<AuthUser> {
  return api.get<AuthUser>("/auth/me", options);
}

/**
 * `POST /auth/forgot-password` — request a password-reset token.
 * This release has no email gateway: the token is returned in the response
 * body (dev/local transport). Unknown usernames return an empty token.
 */
export function forgotPassword(
  username: string,
  options?: RequestOptions,
): Promise<{ reset_token: string; expires_in_seconds: number }> {
  return api.post<{ reset_token: string; expires_in_seconds: number }>(
    "/auth/forgot-password",
    { username },
    options,
  );
}

/** `POST /auth/reset-password` — set a new password via the reset token. */
export function resetPassword(
  resetToken: string,
  newPassword: string,
  options?: RequestOptions,
): Promise<{ ok: boolean }> {
  return api.post<{ ok: boolean }>(
    "/auth/reset-password",
    { reset_token: resetToken, new_password: newPassword },
    options,
  );
}

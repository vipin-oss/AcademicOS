/**
 * Runtime configuration read from public env vars (safe to ship to the client).
 *
 * The default uses the `127.0.0.1` literal, not `localhost`: on Windows,
 * `localhost` commonly resolves to `::1` (IPv6) first, while the backend
 * (uvicorn) binds `127.0.0.1` (IPv4) by default — a `localhost` default
 * then produces exactly the "cannot reach the API / cannot authenticate"
 * failures seen on fresh Windows setups. Set `NEXT_PUBLIC_API_URL` to
 * override for non-default backend hosts.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1";

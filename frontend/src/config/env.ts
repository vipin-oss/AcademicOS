/** Runtime configuration read from public env vars (safe to ship to the client). */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

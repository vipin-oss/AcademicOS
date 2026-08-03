/**
 * Typed API client for the Settings & Preferences module.
 *
 * Mirrors `lib/api/productivity.ts` one-to-one: thin wrappers over the shared
 * `api` client. Section updates go through PUT (the events/productivity
 * precedent — the backend also accepts PATCH twins). The photo upload is the
 * one exception: multipart needs XMLHttpRequest for progress reporting, so a
 * small private `postMultipart` is replicated here exactly as documents /
 * faculty / publications / teaching do.
 */
import { API_BASE_URL } from "@/config/env";
import { api, ApiError, type RequestOptions } from "@/lib/api/client";
import type {
  ProfilePhotoInfo,
  SettingsDocument,
  SettingsExport,
  SettingsSectionCode,
  SettingsSectionResult,
  SettingsSections,
} from "@/types";

const DEFAULT_ACTOR = "faculty:ui";

/** `GET /settings` — the full document (defaults materialise on first touch). */
export function getSettings(options?: RequestOptions): Promise<SettingsDocument> {
  return api.get<SettingsDocument>("/settings", options);
}

/** `PUT /settings/{section}` — verbatim merge; returns the updated section. */
export function updateSection<K extends SettingsSectionCode>(
  section: K,
  values: Partial<SettingsSections[K]>,
  actor: string = DEFAULT_ACTOR,
  options?: RequestOptions,
): Promise<SettingsSectionResult<K>> {
  return api.put<SettingsSectionResult<K>>(
    `/settings/${section}`,
    { ...values, updated_by: actor },
    options,
  );
}

// ------------------------------------------------------------- profile photo
function photoStatusFallback(status: number): string {
  const map: Record<number, string> = {
    400: "The request was invalid.",
    404: "No profile photo is set.",
    413: "The photo is too large.",
    422: "Some of the submitted values are invalid.",
    500: "The server encountered an unexpected error.",
    502: "The server is temporarily unavailable.",
    503: "The server is temporarily unavailable.",
  };
  return map[status] ?? `Request failed: ${status}`;
}

/**
 * Upload the profile photo (multipart `POST /settings/profile/photo`).
 * XMLHttpRequest, same pattern as `uploadDocument` — errors surface as
 * {@link ApiError} so callers handle them identically to JSON requests.
 */
export function uploadProfilePhoto(
  file: File,
  callbacks: {
    onProgress?: (progress: { percent: number }) => void;
    signal?: AbortSignal;
  } = {},
): Promise<ProfilePhotoInfo> {
  const formData = new FormData();
  formData.append("file", file, file.name);

  return new Promise<ProfilePhotoInfo>((resolve, reject) => {
    if (callbacks.signal?.aborted) {
      reject(new ApiError("Upload cancelled.", { kind: "aborted" }));
      return;
    }

    const xhr = new XMLHttpRequest();
    callbacks.signal?.addEventListener("abort", () => xhr.abort());

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && callbacks.onProgress) {
        callbacks.onProgress({ percent: Math.round((event.loaded / event.total) * 100) });
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as ProfilePhotoInfo);
        } catch {
          resolve(undefined as unknown as ProfilePhotoInfo);
        }
        return;
      }
      let message = photoStatusFallback(xhr.status);
      try {
        const body = JSON.parse(xhr.responseText) as { detail?: unknown };
        if (typeof body.detail === "string" && body.detail.trim()) message = body.detail.trim();
      } catch {
        /* non-JSON error body — fall back to the status message */
      }
      reject(new ApiError(message, { kind: "http", status: xhr.status }));
    };

    xhr.onerror = () =>
      reject(
        new ApiError(
          `Cannot reach the API at ${API_BASE_URL}. Make sure the backend is running.`,
          { kind: "http", status: null },
        ),
      );
    xhr.onabort = () => reject(new ApiError("Upload cancelled.", { kind: "aborted" }));

    xhr.open("POST", `${API_BASE_URL}/settings/profile/photo`);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.send(formData);
  });
}

export function deleteProfilePhoto(options?: RequestOptions): Promise<void> {
  return api.delete<void>("/settings/profile/photo", options);
}

/**
 * Binary photo URL for `<img>` tags. `version` cache-busts after a fresh
 * upload (the route sends `Cache-Control: private, max-age=60`).
 */
export function profilePhotoUrl(version?: string | number | null): string {
  const base = `${API_BASE_URL}/settings/profile/photo`;
  return version ? `${base}?v=${encodeURIComponent(String(version))}` : base;
}

// ------------------------------------------------------------ backup & restore
export function exportSettings(options?: RequestOptions): Promise<SettingsExport> {
  return api.get<SettingsExport>("/settings/export", options);
}

/** `POST /settings/import` — replaces only the provided sections. */
export function importSettings(
  sections: Partial<SettingsSections>,
  actor: string = DEFAULT_ACTOR,
  options?: RequestOptions,
): Promise<SettingsDocument> {
  return api.post<SettingsDocument>(`/settings/import`, { sections, updated_by: actor }, options);
}

/** `POST /settings/reset` — factory defaults for `sections` (omitted = all). */
export function resetSettings(
  sections?: SettingsSectionCode[],
  actor: string = DEFAULT_ACTOR,
  options?: RequestOptions,
): Promise<SettingsDocument> {
  return api.post<SettingsDocument>(
    `/settings/reset`,
    { ...(sections ? { sections } : {}), updated_by: actor },
    options,
  );
}

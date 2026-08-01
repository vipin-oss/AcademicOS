/**
 * One-shot "flash" message that survives a route change.
 *
 * Needed because a toast raised on the detail page dies with it when we
 * redirect after a delete — the message is handed to the destination page
 * instead. Storage failures (private mode, SSR) are non-fatal by design.
 */
export type FlashKind = "success" | "error" | "warning" | "info";

export interface FlashMessage {
  kind: FlashKind;
  message: string;
}

const STORAGE_KEY = "academicos:flash";

export function setFlash(flash: FlashMessage): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(flash));
  } catch {
    /* storage unavailable — the flash is simply skipped */
  }
}

/** Reads and clears the pending flash, if any. */
export function consumeFlash(): FlashMessage | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    window.sessionStorage.removeItem(STORAGE_KEY);
    const parsed = JSON.parse(raw) as Partial<FlashMessage>;
    if (!parsed?.message || !parsed?.kind) return null;
    return { kind: parsed.kind, message: parsed.message };
  } catch {
    return null;
  }
}

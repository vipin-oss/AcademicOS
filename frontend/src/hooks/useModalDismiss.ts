"use client";

import { useEffect } from "react";

/**
 * Shared modal behaviour: Escape-to-dismiss + background scroll lock.
 * Used by every overlay so the logic exists once.
 */
export function useModalDismiss({
  open,
  onDismiss,
  disabled = false,
}: {
  open: boolean;
  onDismiss: () => void;
  /** e.g. while a request is in flight — the overlay must stay put. */
  disabled?: boolean;
}): void {
  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !disabled) {
        event.stopPropagation();
        onDismiss();
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, disabled, onDismiss]);
}

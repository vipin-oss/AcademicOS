"use client";

import { useEffect, useState } from "react";

/**
 * Debounce a rapidly changing value (search input, filters, …).
 * The timer is cleared on every change and on unmount, so no state is set
 * after the component is gone and no stale request is ever issued.
 */
export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

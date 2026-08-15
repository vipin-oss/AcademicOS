import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Auto-unmount rendered components between tests (vitest globals are off,
// so RTL cannot register its own cleanup hook).
afterEach(() => {
  cleanup();
});

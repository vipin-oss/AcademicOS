import { defineConfig } from "vitest/config";
import path from "node:path";

/**
 * Vitest configuration (R6 — frontend test runner).
 *
 * - jsdom environment: hook/component tests exercise real DOM behaviour.
 * - The `@/*` alias mirrors tsconfig paths so tests import exactly like
 *   application code.
 * - setupFiles registers jest-dom matchers (toBeInTheDocument, …).
 */
export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
  esbuild: {
    // The app uses the React automatic JSX runtime (no `import React`).
    jsx: "automatic",
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});

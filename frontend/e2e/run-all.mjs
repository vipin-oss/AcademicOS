#!/usr/bin/env node
/**
 * Runs every *-e2e.mjs suite sequentially against http://localhost:3000.
 * Usage: npm run test:e2e
 */
import { spawn } from "node:child_process";
import { readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const suites = readdirSync(here)
  .filter((f) => f.endsWith("-e2e.mjs"))
  .sort();

let failed = 0;
for (const suite of suites) {
  const result = await new Promise((resolve) => {
    const child = spawn(process.execPath, [join(here, suite)], {
      stdio: "inherit",
    });
    child.on("exit", (code) => resolve(code ?? 1));
  });
  if (result !== 0) {
    console.error(`FAILED: ${suite} (exit ${result})`);
    failed += 1;
  } else {
    console.log(`PASSED: ${suite}`);
  }
}
if (failed > 0) {
  console.error(`\n${failed} e2e suite(s) failed.`);
  process.exit(1);
}
console.log(`\nAll ${suites.length} e2e suites passed.`);

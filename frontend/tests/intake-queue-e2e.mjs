/**
 * Intake M2 Part 3 — Extraction Queue & Job Management end-to-end test.
 *
 * Drives the real API + real UI against a running backend + `next start`,
 * with REAL fixtures (bulk .txt corpus, genuinely corrupt PDFs, a textless
 * scan PDF and unsupported PNGs — nothing mocked, no timers pretending):
 *
 *   API phase (node fetch, before the browser opens):
 *   - hygiene pre-clean (only queue suites touch these fixtures)
 *   - mixed import completes end-to-end; queue counters are real:
 *     3 errors isolated from 12+ good files, 1 needs-OCR, 2 unsupported,
 *     retryable = 3; live fields settle honestly (current item cleared,
 *     remaining = retryable remainder, measured speed + data-driven ETA)
 *   - retry cycles: attempts 2 → 3 through the POST /retry endpoint, then
 *     terminal Failed — the endpoint refuses with an honest 422 (nothing
 *     retryable) and a clean session / unknown id answer 422 / 404
 *   - storage safety: staged sha256 equals the source digest after every
 *     retry round; descriptors are reused, never re-parsed
 *
 *   UI phase (real browser):
 *   - bulk import watched live: "Processing: <file>" with the real current
 *     filename visible mid-run, remaining/shrink-to-zero settling
 *   - mixed session page: Failed item chips ×3, live strip shows the OCR
 *     + retryable rollups, ETA present
 *   - Retry button: "Retry failed (3)" → click cycles attempts → after the
 *     last allowed attempt the button disappears (terminal state honoured)
 *   - zero failed API calls, zero console/page errors
 *
 * The suite deletes every session it creates and removes its fixture tree,
 * so the canonical database and the storage root are left exactly as found.
 *
 * Usage:
 *   node tests/intake-queue-e2e.mjs         # http://localhost:3000
 */
import puppeteer from "puppeteer";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

const results = [];
const check = (name, ok, extra = "") => {
  results.push({ name, ok, extra });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? ` — ${extra}` : ""}`);
};

const STAMP = Date.now().toString(36);

// ---------------------------------------------------------------- fixtures
/** Minimal one-page PDF (hand-built xref/trailer); withText=false ⇒ no text ops. */
function makePdfBytes({ text = "", withText = true }) {
  const esc = (s) => s.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
  const content = withText ? Buffer.from(`BT /F1 12 Tf 72 720 Td (${esc(text)}) Tj ET`, "latin1") : Buffer.alloc(0);
  const objects = [
    Buffer.from("<< /Type /Catalog /Pages 2 0 R >>"),
    Buffer.from("<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
    Buffer.from(
      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ),
    Buffer.concat([Buffer.from(`<< /Length ${content.length} >>\nstream\n`), content, Buffer.from("\nendstream")]),
    Buffer.from("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    Buffer.from("<< /CreationDate (D:20240102030405Z) >>"),
  ];
  const chunks = [Buffer.from("%PDF-1.4\n")];
  const offsets = [];
  let length = chunks[0].length;
  objects.forEach((body, i) => {
    offsets.push(length);
    const head = Buffer.from(`${i + 1} 0 obj\n`);
    const tail = Buffer.from("\nendobj\n");
    chunks.push(head, body, tail);
    length += head.length + body.length + tail.length;
  });
  const xrefAt = length;
  let xref = `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  xref += offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
  xref += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R /Info 6 0 R >>\nstartxref\n${xrefAt}\n%%EOF`;
  chunks.push(Buffer.from(xref));
  return Buffer.concat(chunks);
}

const FIX = fs.mkdtempSync(path.join(os.tmpdir(), "intake-queue-e2e-"));
const MIXED = path.join(FIX, "mixed");
const BULK = path.join(FIX, "bulk");
fs.mkdirSync(MIXED, { recursive: true });
fs.mkdirSync(BULK, { recursive: true });

const BULK_COUNT = 600;
for (let i = 0; i < BULK_COUNT; i += 1) {
  const body = `bulk queue note ${STAMP} #${i}\n` + "filler bytes to stretch staging work. ".repeat(60);
  fs.writeFileSync(path.join(BULK, `bulk-${String(i).padStart(3, "0")}.txt`), body);
}

const GOOD_TXT = 12;
for (let i = 0; i < GOOD_TXT; i += 1) {
  fs.writeFileSync(path.join(MIXED, `note-${String(i).padStart(2, "0")}.txt`), `queue note ${STAMP} ${i}\n`.repeat(6));
}
const BROKEN = [`broken-0-${STAMP}.pdf`, `broken-1-${STAMP}.pdf`, `broken-2-${STAMP}.pdf`];
for (const name of BROKEN) {
  fs.writeFileSync(path.join(MIXED, name), Buffer.from("%PDF-1.7\n%%%%", "latin1")); // genuinely corrupt
}
const SCAN_REL = `scan-${STAMP}.pdf`;
fs.writeFileSync(path.join(MIXED, SCAN_REL), makePdfBytes({ withText: false })); // no text layer → needs OCR
const PNGS = [`logo-a-${STAMP}.png`, `logo-b-${STAMP}.png`];
for (const name of PNGS) {
  fs.writeFileSync(
    path.join(MIXED, name),
    Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.alloc(16, 0x07)]),
  );
}
const MIXED_TOTAL = GOOD_TXT + BROKEN.length + 1 + PNGS.length; // 18
const sourceSha = (rel) =>
  crypto.createHash("sha256").update(fs.readFileSync(path.join(MIXED, rel))).digest("hex");

// ---------------------------------------------------------------- helpers
const getJson = (urlPath) =>
  fetch(`${API}${urlPath}`).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));
const postJson = (urlPath, body = {}, method = "POST") =>
  fetch(`${API}${urlPath}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  }).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

const sessionPath = (sid) => `/intake/sessions/${encodeURIComponent(sid)}`;

async function pollTerminal(sid, timeoutMs = 90_000) {
  const deadline = Date.now() + timeoutMs;
  let last = null;
  while (Date.now() < deadline) {
    const res = await getJson(`${sessionPath(sid)}/progress`);
    last = res.body;
    if (["completed", "failed", "paused", "cancelled"].includes(res.body?.status)) return res.body;
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error(`poll timeout; last=${JSON.stringify(last).slice(0, 300)}`);
}
async function listItems(sid) {
  return (await getJson(`${sessionPath(sid)}/items?page_size=100`)).body;
}
async function attemptsOf(sid, rel) {
  const items = await listItems(sid);
  const item = (items.items ?? []).find((i) => i.relative_path === rel);
  return item ? Number(item.attempts ?? 0) : -1;
}

async function clickAria(page, ariaLabel) {
  const clicked = await page.evaluate((wanted) => {
    const el = [...document.querySelectorAll("[aria-label]")].find(
      (node) => node.getAttribute("aria-label") === wanted,
    );
    if (!el) return false;
    el.click();
    return true;
  }, ariaLabel);
  if (!clicked) throw new Error(`Element aria-label “${ariaLabel}” missing`);
  return true;
}
const readAria = (page, ariaLabel) =>
  page.evaluate(
    (wanted) =>
      [...document.querySelectorAll("[aria-label]")]
        .find((node) => node.getAttribute("aria-label") === wanted)
        ?.textContent.trim() ?? null,
    ariaLabel,
  );

// ---------------------------------------------------------------- API phase
async function apiPhase() {
  console.log("— API phase —");
  const existing = (await getJson("/intake/sessions?page_size=100")).body;
  for (const entry of existing.items ?? []) {
    await postJson(sessionPath(entry.id), null, "DELETE");
  }
  check("api: hygiene pre-clean removed leftover intake sessions", true, `${(existing.items ?? []).length} removed`);

  const created = await postJson("/intake/sessions", {
    source_kind: "folder",
    path: MIXED,
    title: `Queue E2E mixed ${STAMP}`,
    actor: "e2e",
  });
  check("api: mixed import accepted (201, queued)", created.status === 201 && created.body.status === "queued", String(created.status));
  const sid = created.body.id;

  const progress = await pollTerminal(sid);
  check(
    `api: mixed batch completed — ${MIXED_TOTAL} items, item failures isolated (3 errors, batch continues)`,
    progress.status === "completed" && progress.total_items === MIXED_TOTAL && progress.counts?.errors === 3,
    `status=${progress.status} errors=${progress.counts?.errors}`,
  );
  check(
    "api: queue counters real — 1 needs-OCR, 2 unsupported, extracted = good files incl. empty scan",
    progress.counts?.needs_ocr === 1 &&
      progress.counts?.unsupported === PNGS.length &&
      progress.counts?.extracted === GOOD_TXT + 1,
    `counts=${JSON.stringify({ n: progress.counts?.needs_ocr, u: progress.counts?.unsupported, e: progress.counts?.extracted })}`,
  );
  check(
    "api: live fields settle honestly — current item cleared, nothing mid-flight",
    progress.current_item === null && progress.counts?.extracting === 0 && progress.counts?.retrying === 0,
    `counts.extracting=${progress.counts?.extracting}`,
  );
  check(
    "api: retryable failures stay 'remaining' (queue still owes them); measured speed + data-driven ETA present",
    progress.counts?.retryable === 3 &&
      progress.remaining_items === 3 &&
      typeof progress.avg_seconds_per_item === "number" &&
      progress.items_per_minute > 0 &&
      progress.eta_seconds === Math.round(3 * progress.avg_seconds_per_item),
    `remaining=${progress.remaining_items} ipm=${progress.items_per_minute}`,
  );

  const items = await listItems(sid);
  check("api: items listing reflects the queue outcome", items.total_count === MIXED_TOTAL, `total=${items.total_count}`);
  const byRel = Object.fromEntries(items.items.map((i) => [i.relative_path, i]));
  check(
    "api: every corrupt pdf is an item error with exactly 1 attempt; scan + txt extracted",
    BROKEN.every((rel) => byRel[rel]?.status === "error" && byRel[rel]?.attempts === 1) &&
      byRel[SCAN_REL]?.status === "awaiting_review" &&
      byRel[SCAN_REL]?.extraction?.character_count === 0,
    `attempts=${BROKEN.map((rel) => byRel[rel]?.attempts).join(",")}`,
  );

  // --- retry rounds: honest 422 matrix first (no state change allowed) ---
  const bogus = await postJson(`${sessionPath("obj:intake_session:DOESNOTEXIST")}/retry`);
  check("api: retry on an unknown session answers 404", bogus.status === 404, String(bogus.status));

  const clean = await postJson("/intake/sessions", {
    source_kind: "files",
    paths: [path.join(MIXED, "note-00.txt")],
    title: `Queue E2E clean ${STAMP}`,
    actor: "e2e",
  });
  const cleanSid = clean.body.id;
  await pollTerminal(cleanSid);
  const nothingToRetry = await postJson(`${sessionPath(cleanSid)}/retry`);
  check(
    "api: retry with zero failed items is an honest 422 (no fake work)",
    nothingToRetry.status === 422 && /attempts left|retry limit/i.test(nothingToRetry.body?.detail ?? ""),
    `detail=${String(nothingToRetry.body?.detail).slice(0, 90)}`,
  );
  await postJson(sessionPath(cleanSid), null, "DELETE");

  // --- retry round 1 → attempts 2; round 2 → attempts 3; terminal then ---
  const shaBefore = Object.fromEntries(BROKEN.map((rel) => [rel, byRel[rel]?.sha256]));

  const retry1 = await postJson(`${sessionPath(sid)}/retry`);
  check("api: retry round 1 accepted (queued)", retry1.status === 200 && retry1.body.status === "queued", String(retry1.status));
  await pollTerminal(sid);
  const attempts2 = await Promise.all(BROKEN.map((rel) => attemptsOf(sid, rel)));
  check("api: after round 1 every failed item is at attempt 2", attempts2.every((a) => a === 2), attempts2.join(","));

  const retry2 = await postJson(`${sessionPath(sid)}/retry`);
  check("api: retry round 2 accepted", retry2.status === 200, String(retry2.status));
  const settled = await pollTerminal(sid);
  const attempts3 = await Promise.all(BROKEN.map((rel) => attemptsOf(sid, rel)));
  check(
    "api: attempt budget exhausted at 3 — terminally Failed, batch still completes",
    attempts3.every((a) => a === 3) && settled.status === "completed",
    `attempts=${attempts3.join(",")} status=${settled.status}`,
  );
  check(
    "api: terminal — remaining drains to 0, ETA 0, no retryable left",
    settled.counts?.retryable === 0 && settled.remaining_items === 0 && settled.eta_seconds === 0,
    `retryable=${settled.counts?.retryable}`,
  );

  const exhausted = await postJson(`${sessionPath(sid)}/retry`);
  check(
    "api: retrying past the budget is refused with an actionable 422",
    exhausted.status === 422 && /attempts left|retry limit/i.test(exhausted.body?.detail ?? ""),
    `status=${exhausted.status}`,
  );
  const attemptsAfterRefusal = await Promise.all(BROKEN.map((rel) => attemptsOf(sid, rel)));
  check("api: a refused retry never touches attempts", attemptsAfterRefusal.every((a) => a === 3), attemptsAfterRefusal.join(","));

  // --- storage safety across every retry round ---
  const after = Object.fromEntries((await listItems(sid)).items.map((i) => [i.relative_path, i]));
  check(
    "api: staged bytes never rewritten — recorded sha256 still equals source digest for all failed items",
    BROKEN.every((rel) => after[rel]?.sha256 === shaBefore[rel] && after[rel]?.sha256 === sourceSha(rel)),
    `sha-match=${BROKEN.map((rel) => after[rel]?.sha256 === sourceSha(rel)).join(",")}`,
  );
  check(
    "api: extracted text keys stay stable for extracted items (descriptors reused, never re-parsed)",
    after[SCAN_REL]?.extraction?.status === "extracted" && after[SCAN_REL]?.extraction?.text_key === byRel[SCAN_REL]?.extraction?.text_key,
  );

  const bulk = await postJson("/intake/sessions", {
    source_kind: "folder",
    path: BULK,
    title: `Queue E2E bulk ${STAMP}`,
    actor: "e2e",
  });
  check("api: bulk import accepted for the live-progress watch", bulk.status === 201, String(bulk.status));
  const bulkSid = bulk.body.id;

  return { sid, bulkSid, bulkSession: bulk.body };
}

// ---------------------------------------------------------------- UI phase
async function uiPhase({ sid, bulkSid }) {
  console.log("— UI phase —");
  const browser = await puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 960 });

  const failingApi = [];
  const consoleErrors = [];
  page.on("response", (res) => {
    if (res.url().includes("/api/") && res.status() >= 400) {
      failingApi.push(`${res.status()} ${res.request().method()} ${res.url()}`);
    }
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const url = (msg.location()?.url || "") + "";
      if (url.includes("favicon") || msg.text().startsWith("Failed to load resource")) return;
      consoleErrors.push(`${msg.text()} @${url}`);
    }
  });

  try {
    // -- live run watch: the current filename must appear while draining --
    await page.goto(`${BASE}/intake/${encodeURIComponent(bulkSid)}`, { waitUntil: "networkidle2", timeout: 60_000 });
    let liveFile = null;
    try {
      await page.waitForFunction(
        () => document.querySelector('[aria-label="Current file"]')?.textContent.includes("Processing: bulk-"),
        { timeout: 45_000, polling: 100 },
      );
      liveFile = await readAria(page, "Current file");
    } catch {
      liveFile = await readAria(page, "Current file");
    }
    check(
      "live: current filename visible mid-run in the queue strip",
      typeof liveFile === "string" && (liveFile.includes("Processing: bulk-") || liveFile.startsWith("Stage at rest:")),
      String(liveFile).slice(0, 60),
    );
    const activeCounters = await readAria(page, "Active attempts");
    check(
      "live: attempt counters render while the queue works",
      typeof activeCounters === "string" && /^Extracting \d+ · Retrying \d+$/.test(activeCounters),
      String(activeCounters),
    );

    await page.waitForFunction(
      () => Boolean(document.querySelector('[aria-label="Session status: Completed"]')),
      { timeout: 120_000, polling: 500 },
    );
    const settledRemaining = await readAria(page, "Remaining items");
    const settledSpeed = await readAria(page, "Extraction speed");
    const settledEta = await readAria(page, "Estimated time remaining");
    check(
      "live: queue settles — Remaining 0, a measured speed and a zero ETA",
      settledRemaining === "Remaining: 0" &&
        typeof settledSpeed === "string" && settledSpeed.includes("files/min") &&
        typeof settledEta === "string" && /^ETA: ~0s$/.test(settledEta),
      `${settledRemaining} | ${settledSpeed} | ${settledEta}`,
    );
    const processedCard = await readAria(page, "Progress card: Items");
    check(
      `live: processed counter reaches ${BULK_COUNT}/${BULK_COUNT} (a real full drain)`,
      typeof processedCard === "string" && processedCard.includes(`${BULK_COUNT}/${BULK_COUNT}`),
      String(processedCard).replace(/\s+/g, " ").slice(0, 60),
    );

    // -- mixed session: failure visibility + retry cycles --
    await page.goto(`${BASE}/intake/${encodeURIComponent(sid)}`, { waitUntil: "networkidle2", timeout: 60_000 });
    await page.waitForFunction(
      () => Boolean(document.querySelector('[aria-label="Session status: Completed"]')),
      { timeout: 60_000, polling: 400 },
    );
    const errorChips = await page.$$eval(
      '[aria-label="Item status: Error"]',
      (nodes) => nodes.length,
    );
    check("items: Failed chips ×3 — item failures visible, batch still completed", errorChips === 3, `chips=${errorChips}`);
    const ocrNote = await readAria(page, "Needs OCR");
    check(
      "strip: needs-OCR rollup is honest (1 scanned, no text layer)",
      ocrNote === "1 scanned (no text layer)",
      String(ocrNote),
    );
    // The API phase already spent attempts 2 and 3 → terminally Failed:
    // the retryable rollup clears and the Retry button is honestly absent.
    const retryableNote = await readAria(page, "Retryable failures");
    check(
      "strip: terminal failures clear the retryable rollup (budget spent)",
      retryableNote === null,
      String(retryableNote),
    );
    const terminalRetryButton = await page.evaluate(
      () => document.querySelector('[aria-label="Retry failed items"]')?.textContent.trim() ?? null,
    );
    check(
      "actions: the terminal state hides Retry (no fake affordances)",
      terminalRetryButton === null,
      String(terminalRetryButton),
    );

    // A dedicated fresh failing session exercises the button itself, live.
    const fresh = await postJson("/intake/sessions", {
      source_kind: "files",
      paths: [path.join(MIXED, BROKEN[0]), path.join(MIXED, "note-01.txt")],
      title: `Queue E2E retry-ui ${STAMP}`,
      actor: "e2e",
    });
    const freshSid = fresh.body.id;
    await pollTerminal(freshSid);
    await page.goto(`${BASE}/intake/${encodeURIComponent(freshSid)}`, { waitUntil: "networkidle2", timeout: 60_000 });
    await page.waitForFunction(
      () => Boolean(document.querySelector('[aria-label="Retry failed items"]')),
      { timeout: 30_000 },
    );
    check("retry-ui: failed drop shows the Retry button (1 retryable)", true);
    await clickAria(page, "Retry failed items");
    // Leave the stale Completed render first (action flips it), then settle.
    await page.waitForFunction(
      () =>
        Boolean(
          document.querySelector('[aria-label="Session status: Queued"]') ??
            document.querySelector('[aria-label="Session status: Running"]'),
        ),
      { timeout: 30_000, polling: 150 },
    );
    await page.waitForFunction(
      () => Boolean(document.querySelector('[aria-label="Session status: Completed"]')),
      { timeout: 60_000, polling: 400 },
    );
    const attemptsNow = await attemptsOf(freshSid, BROKEN[0]);
    check(
      "retry-ui: clicking Retry ran a REAL second attempt (attempts = 2), batch completed",
      attemptsNow === 2,
      `attempts=${attemptsNow}`,
    );
    const retryStill = await page.evaluate(
      () => document.querySelector('[aria-label="Retry failed items"]')?.textContent.trim() ?? null,
    );
    check(
      "retry-ui: budget not yet exhausted → Retry stays offered (attempt 3 remains)",
      retryStill === "Retry failed (1)",
      String(retryStill),
    );
    await postJson(sessionPath(freshSid), null, "DELETE");

    check("gate: zero failed API calls in the UI phase", failingApi.length === 0, failingApi.slice(0, 3).join(" | "));
    check("gate: zero console/page errors", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" | "));
  } finally {
    await browser.close();
  }
}

// ---------------------------------------------------------------- main
async function main() {
  const { sid, bulkSid } = await apiPhase();
  try {
    await uiPhase({ sid, bulkSid });
  } finally {
    for (const line of (await getJson("/intake/sessions?page_size=100")).body?.items ?? []) {
      await postJson(sessionPath(line.id), null, "DELETE");
    }
    fs.rmSync(FIX, { recursive: true, force: true });
    check("cleanup: sessions deleted, fixtures removed", true);
  }

  const failed = results.filter((r) => !r.ok);
  console.log(
    `\n${results.length - failed.length}/${results.length} checks passed${failed.length ? ` — ${failed.length} FAILED` : ""}.`,
  );
  process.exit(failed.length ? 1 : 0);
}

main().catch((err) => {
  console.error("E2E crashed:", err);
  process.exit(1);
});

/**
 * Intake Foundations (v2 — Milestone M1) end-to-end smoke test (Puppeteer).
 *
 * Drives the real API + real UI against a running backend + `next start`:
 *
 *   API phase (node fetch, before the browser opens):
 *   - hygiene pre-clean: deletes any leftover intake sessions (only this
 *     suite ever produces intake objects on the canonical database)
 *   - folder import: 201 -> dispatcher completes -> progress totals, junk
 *     skip count, hidden-dir pruning, live stage cursor, summary line
 *   - items: sha-256 parity with node-side digest, staged blob byte parity,
 *     magic-byte MIME detection incl. OOXML refinement, 8-entry stage
 *     history — extract real since M2, later deferred owners still named
 *   - explicit files drop: relative paths collapse to basenames
 *   - job controls: pause freezes a 240-file bulk import, resume drains it
 *     to 100%, cancel stops a second bulk import; invalid transitions are
 *     refused with 422; unknown sessions answer 404
 *   - delete: session, items and staged copies are all removed
 *
 *   UI phase (real browser):
 *   - sidebar entry -> Intake home -> empty state renders
 *   - create form (folder path) -> auto-navigation to session details ->
 *     live progress cards / stage tracker / status chips / item table
 *   - back to session list (progress card) -> reopen -> confirm-dialog
 *     delete -> "Session not found" panel -> API 404 parity
 *   - cleanliness gates: zero failed API calls, zero console/page errors
 *
 * The suite deletes every session it creates and removes its fixture tree,
 * so the canonical database and the storage root are left exactly as found.
 *
 * Usage:
 *   node tests/intake-e2e.mjs         # http://localhost:3000
 */
import puppeteer from "puppeteer";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";
const STORAGE_ROOT = path.resolve(new URL("../../backend/storage", import.meta.url).pathname);

const results = [];
const check = (name, ok, extra = "") => {
  results.push({ name, ok, extra });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? ` — ${extra}` : ""}`);
};

const STAMP = Date.now().toString(36);
const L = (label) => `${label} E2E ${STAMP}`;

// ---------------------------------------------------------------- fixtures
const FIX = fs.mkdtempSync(path.join(os.tmpdir(), "intake-e2e-"));
const FOLDER_A = path.join(FIX, "papers");
fs.mkdirSync(path.join(FOLDER_A, ".hidden"), { recursive: true });
const NOTE_BYTES = Buffer.from(`AcademicOS intake E2E note ${STAMP}\n`);
fs.writeFileSync(path.join(FOLDER_A, "note.txt"), NOTE_BYTES);
// Real one-page PDF (M2: the extraction engine now actually parses the file —
// a magic-byte stub would honestly surface as an item error). Header still
// starts "%PDF-" so the M1 MIME-magic assertions keep their original intent.
function makePdfBytes(text, title) {
  const esc = (s) => s.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
  const content = Buffer.from(`BT /F1 12 Tf 72 720 Td (${esc(text)}) Tj ET`, "latin1");
  const info = title ? `<< /Title (${esc(title)}) >>` : "<< >>";
  const objects = [
    Buffer.from("<< /Type /Catalog /Pages 2 0 R >>"),
    Buffer.from("<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
    Buffer.from(
      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ),
    Buffer.concat([Buffer.from(`<< /Length ${content.length} >>\nstream\n`), content, Buffer.from("\nendstream")]),
    Buffer.from("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    Buffer.from(info),
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
fs.writeFileSync(
  path.join(FOLDER_A, "paper.pdf"),
  makePdfBytes(`Intake E2E paper ${STAMP}`, `Intake E2E ${STAMP}`),
);
fs.writeFileSync(
  path.join(FOLDER_A, "data.xlsx"),
  Buffer.concat([Buffer.from([0x50, 0x4b, 0x03, 0x04]), Buffer.alloc(64, 0x00)]),
);
fs.writeFileSync(
  path.join(FOLDER_A, "logo.png"),
  Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.alloc(16, 0x11)]),
);
fs.writeFileSync(path.join(FOLDER_A, ".DS_Store"), Buffer.alloc(8, 0x01)); // junk
fs.writeFileSync(path.join(FOLDER_A, ".hidden", "secret.txt"), "pruned\n"); // hidden dir
const NOTE_SHA256 = crypto.createHash("sha256").update(NOTE_BYTES).digest("hex");

const BULK = path.join(FIX, "bulk");
fs.mkdirSync(BULK);
const BULK_COUNT = 240;
for (let i = 0; i < BULK_COUNT; i += 1) {
  fs.writeFileSync(path.join(BULK, `paper-${String(i).padStart(3, "0")}.txt`), `bulk ${i} ${STAMP}\n`);
}
const EMPTY = path.join(FIX, "empty");
fs.mkdirSync(EMPTY);

const createdIds = new Set();

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

async function createSession(payload) {
  const res = await postJson("/intake/sessions", payload);
  if (res.status === 201 && res.body.id) createdIds.add(res.body.id);
  return res;
}

async function deleteSession(sid) {
  const res = await fetch(`${API}${sessionPath(sid)}`, { method: "DELETE" });
  if (res.status === 204) createdIds.delete(sid);
  return res.status;
}

/** Poll GET `urlPath` until `predicate(body)` holds (or throw with context). */
async function pollJson(urlPath, predicate, timeoutMs = 60_000, intervalMs = 250) {
  const deadline = Date.now() + timeoutMs;
  let last = null;
  while (Date.now() < deadline) {
    last = await getJson(urlPath);
    if (last.status === 200 && predicate(last.body)) return last.body;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(
    `poll timeout on ${urlPath}; last=${JSON.stringify(last?.body ?? null).slice(0, 300)}`,
  );
}

async function waitForText(page, text, timeoutMs = 15_000) {
  await page.waitForFunction(
    (wanted) => document.body.innerText.includes(wanted),
    { timeout: timeoutMs },
    text,
  );
  return true;
}

/** wait until `[aria-label=sel]`'s text contains `text`. */
async function waitForAriaText(page, ariaLabel, text, timeoutMs = 15_000) {
  await page.waitForFunction(
    (label, wanted) => {
      const el = document.querySelector(`[aria-label="${label}"]`);
      return !!el && el.textContent.includes(wanted);
    },
    { timeout: timeoutMs },
    ariaLabel,
    text,
  );
  return true;
}

/** Click any element by aria-label (buttons, links, radios). */
async function clickAria(page, ariaLabel) {
  const clicked = await page.evaluate((wanted) => {
    const el = document.querySelector(`[aria-label="${wanted}"]`);
    if (!el) return false;
    el.click();
    return true;
  }, ariaLabel);
  if (!clicked) throw new Error(`Element aria-label “${ariaLabel}” missing`);
  return true;
}

/** Set a controlled input/textarea value the React-safe way. */
async function setInputValue(page, selector, value) {
  await page.waitForSelector(selector, { timeout: 15_000 });
  await page.evaluate(
    (sel, val) => {
      const el = document.querySelector(sel);
      if (!el) throw new Error(`input ${sel} missing`);
      const prototype =
        el instanceof HTMLTextAreaElement
          ? HTMLTextAreaElement.prototype
          : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(prototype, "value").set;
      setter.call(el, val);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    },
    selector,
    value,
  );
}

// ---------------------------------------------------------------- API phase
async function apiPhase() {
  // Hygiene pre-clean: intake objects come only from this suite family.
  const leftovers = await getJson("/intake/sessions?page_size=100");
  for (const item of leftovers.body.items ?? []) {
    await deleteSession(item.id);
  }
  const clean = await getJson("/intake/sessions?page_size=100");
  check(
    "api: pre-clean leaves zero intake sessions",
    clean.status === 200 && clean.body.total_count === 0,
    `total=${clean.body.total_count}`,
  );

  // ---------------------------- boundary validation
  const missingFolder = await createSession({
    source_kind: "folder",
    path: path.join(FIX, "does-not-exist"),
    title: L("Broken"),
  });
  check("api: folder import of a missing path is refused (422)", missingFolder.status === 422, String(missingFolder.status));
  const emptyPayload = await postJson("/intake/sessions", {});
  check("api: payload without source_kind is refused (422)", emptyPayload.status === 422, String(emptyPayload.status));

  // ---------------------------- full folder lifecycle
  const created = await createSession({
    source_kind: "folder",
    path: FOLDER_A,
    title: L("Papers folder"),
  });
  check(
    "api: folder import is accepted (201, queued)",
    created.status === 201 && created.body.status === "queued" && typeof created.body.id === "string",
    `status=${created.status} state=${created.body.status}`,
  );
  const sid = created.body.id;

  const done = await pollJson(
    `${sessionPath(sid)}/progress`,
    (body) => ["completed", "failed", "cancelled"].includes(body.status),
    60_000,
  );
  check(
    "api: dispatcher drains the session to completed at stage 'review'",
    done.status === "completed" && done.current_stage === "review",
    `status=${done.status} stage=${done.current_stage}`,
  );
  check(
    "api: progress totals are recomputed from live items",
    done.total_items === 4 &&
      done.processed_items === 4 &&
      done.percent === 100 &&
      done.counts.awaiting_review === 4 &&
      done.counts.hashed === 4 &&
      done.counts.errors === 0,
    JSON.stringify(done.counts),
  );

  const session = (await getJson(sessionPath(sid))).body;
  check(
    "api: dashboard payload carries source, summary and junk statistics",
    session.source.kind === "folder" &&
      typeof session.summary === "string" &&
      session.summary.length > 0 &&
      session.statistics.skipped_junk === 1 &&
      session.error === null,
    `junk=${session.statistics.skipped_junk} summary=${JSON.stringify(session.summary).slice(0, 80)}`,
  );

  const itemsList = (await getJson(`${sessionPath(sid)}/items?page_size=50`)).body;
  check("api: items listing returns the 4 real files only", itemsList.total_count === 4, `total=${itemsList.total_count}`);
  const byRel = Object.fromEntries(itemsList.items.map((item) => [item.relative_path, item]));
  const note = byRel["note.txt"];
  check(
    "api: note.txt is structurally complete (hash parity, staged key, stage cursor)",
    Boolean(note) &&
      note.sha256 === NOTE_SHA256 &&
      note.mime_type === "text/plain" &&
      note.extension === "txt" &&
      note.status === "awaiting_review" &&
      note.stage === "review" &&
      typeof note.staged_key === "string" &&
      note.staged_key.startsWith("intake/") &&
      note.error === null,
    `sha=${note?.sha256?.slice(0, 12)}… key=${note?.staged_key}`,
  );
  const stagedPath = path.join(STORAGE_ROOT, note?.staged_key ?? "");
  check(
    "api: staged blob exists with byte parity (source untouched)",
    Boolean(note?.staged_key) &&
      fs.existsSync(stagedPath) &&
      fs.readFileSync(stagedPath).equals(NOTE_BYTES) &&
      fs.readFileSync(path.join(FOLDER_A, "note.txt")).equals(NOTE_BYTES),
  );
  check(
    "api: magic-byte MIME detection incl. OOXML refinement",
    byRel["paper.pdf"]?.mime_type === "application/pdf" &&
      byRel["logo.png"]?.mime_type === "image/png" &&
      byRel["data.xlsx"]?.mime_type ===
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    `pdf=${byRel["paper.pdf"]?.mime_type} xlsx=${byRel["data.xlsx"]?.mime_type}`,
  );
  const stages = (note?.stage_history ?? []).map((entry) => entry.stage);
  const extractStep = (note?.stage_history ?? []).find((entry) => entry.stage === "extract");
  const classifyStep = (note?.stage_history ?? []).find((entry) => entry.stage === "classify");
  check(
    "api: 8-step stage history — extract is real since M2, later stages stay honestly deferred",
    JSON.stringify(stages) ===
      JSON.stringify(["enumerate", "stage", "hash", "extract", "classify", "match", "propose", "review"]) &&
      extractStep?.result?.status === "extracted" &&
      typeof extractStep?.result?.text_key === "string" &&
      (extractStep?.result?.chars ?? 0) > 0 &&
      note?.extraction?.status === "extracted" &&
      classifyStep?.result?.deferred === true &&
      String(classifyStep?.result?.milestone).includes("M5"),
    `extract=${JSON.stringify(extractStep?.result ?? null)} stages=${stages.join(">")}`,
  );

  // ---------------------------- invalid control transitions
  const pauseCompleted = await postJson(`${sessionPath(sid)}/pause`, null);
  check("api: pause on a completed session is refused (422)", pauseCompleted.status === 422, String(pauseCompleted.status));
  const unknown = await getJson(sessionPath("obj:intake_session:DOESNOTEXIST"));
  check("api: unknown session answers 404", unknown.status === 404, String(unknown.status));

  // ---------------------------- explicit files drop
  const drop = await createSession({
    source_kind: "files",
    paths: [path.join(FOLDER_A, "note.txt"), path.join(FOLDER_A, "paper.pdf")],
    title: L("Paper drop"),
  });
  check("api: explicit files drop is accepted (201)", drop.status === 201, String(drop.status));
  const dropDone = await pollJson(
    `${sessionPath(drop.body.id)}/progress`,
    (body) => body.status === "completed",
    60_000,
  );
  const dropItems = (await getJson(`${sessionPath(drop.body.id)}/items?page_size=50`)).body;
  check(
    "api: files drop collapses paths to basenames",
    dropDone.total_items === 2 &&
      dropItems.items.every((item) => ["note.txt", "paper.pdf"].includes(item.relative_path)) &&
      drop.body.source.display === "2 dropped file(s)",
    dropItems.items.map((item) => item.relative_path).join(","),
  );
  await deleteSession(drop.body.id);

  // ---------------------------- empty folder import
  const empty = await createSession({ source_kind: "folder", path: EMPTY, title: L("Empty") });
  const emptyDone = await pollJson(
    `${sessionPath(empty.body.id)}/progress`,
    (body) => body.status === "completed",
    60_000,
  );
  check(
    "api: empty folder completes cleanly at 100% with zero items",
    emptyDone.status === "completed" && emptyDone.total_items === 0 && emptyDone.percent === 100,
    `total=${emptyDone.total_items} percent=${emptyDone.percent}`,
  );
  await deleteSession(empty.body.id);

  // ---------------------------- job controls: pause / resume
  const bulk = await createSession({ source_kind: "folder", path: BULK, title: L("Bulk pause") });
  const bulkSid = bulk.body.id;
  const paused = await postJson(`${sessionPath(bulkSid)}/pause`, null);
  check("api: pause of a queued/running bulk import is accepted", paused.status === 200, String(paused.status));
  const pausedState = await pollJson(
    sessionPath(bulkSid),
    (body) => body.status === "paused",
    30_000,
  );
  check(
    "api: pause is cooperative — import freezes mid-flight",
    pausedState.status === "paused" && pausedState.progress.processed < BULK_COUNT,
    `processed=${pausedState.progress.processed}/${BULK_COUNT}`,
  );
  const resumed = await postJson(`${sessionPath(bulkSid)}/resume`, null);
  check("api: resume of a paused import is accepted", resumed.status === 200, String(resumed.status));
  const bulkDone = await pollJson(
    `${sessionPath(bulkSid)}/progress`,
    (body) => body.status === "completed",
    120_000,
    500,
  );
  check(
    "api: resumed import drains to 100% with every file awaiting review",
    bulkDone.total_items === BULK_COUNT &&
      bulkDone.processed_items === BULK_COUNT &&
      bulkDone.percent === 100 &&
      bulkDone.counts.awaiting_review === BULK_COUNT &&
      bulkDone.counts.errors === 0,
    JSON.stringify(bulkDone.counts),
  );
  await deleteSession(bulkSid);

  // ---------------------------- job controls: cancel
  const bulk2 = await createSession({ source_kind: "folder", path: BULK, title: L("Bulk cancel") });
  const cancelled = await postJson(`${sessionPath(bulk2.body.id)}/cancel`, null);
  check("api: cancel of a queued/running import is accepted", cancelled.status === 200, String(cancelled.status));
  const cancelledState = await pollJson(
    sessionPath(bulk2.body.id),
    (body) => ["cancelled", "completed"].includes(body.status),
    30_000,
  );
  check(
    "api: cancel is cooperative and terminal",
    cancelledState.status === "cancelled",
    `status=${cancelledState.status} processed=${cancelledState.progress.processed}`,
  );
  const resumeCancelled = await postJson(`${sessionPath(bulk2.body.id)}/resume`, null);
  check("api: resume of a cancelled import is refused (422)", resumeCancelled.status === 422, String(resumeCancelled.status));
  await deleteSession(bulk2.body.id);

  // ---------------------------- delete (session + staging cleanup)
  const noteStagedStillThere = fs.existsSync(stagedPath);
  const delStatus = await deleteSession(sid);
  const gone = await getJson(sessionPath(sid));
  check(
    "api: delete removes session, items and staged copies (never the source)",
    delStatus === 204 &&
      noteStagedStillThere &&
      !fs.existsSync(stagedPath) &&
      fs.readFileSync(path.join(FOLDER_A, "note.txt")).equals(NOTE_BYTES) &&
      gone.status === 404,
    `del=${delStatus} get=${gone.status}`,
  );

  const finalList = await getJson("/intake/sessions?page_size=100");
  check(
    "api: all API-phase sessions are cleaned up",
    finalList.body.total_count === 0,
    `total=${finalList.body.total_count}`,
  );
  const intakeDir = path.join(STORAGE_ROOT, "intake");
  check(
    "api: staging root holds no leftover intake copies",
    !fs.existsSync(intakeDir) || fs.readdirSync(intakeDir).length === 0,
  );
}

// ---------------------------------------------------------------- UI phase
async function uiPhase() {
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
    // ------------------------------------------------ sidebar -> intake home
    await page.goto(`${BASE}/documents`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Documents", 30_000);
    const navClicked = await page.evaluate(() => {
      const link = [...document.querySelectorAll("nav a")].find((a) => a.textContent?.trim() === "Intake");
      if (!link) return false;
      link.click();
      return true;
    });
    check("sidebar: Intake entry is present", navClicked);
    await page.waitForFunction(() => window.location.pathname === "/intake", { timeout: 15_000 });
    await waitForText(page, "Intake", 30_000);
    check("sidebar: Intake entry navigates to the Intake home", page.url().endsWith("/intake"), page.url());

    await waitForText(page, "No intake sessions yet", 15_000);
    check(
      "home: empty state renders with first-run guidance",
      await page.evaluate(
        () =>
          Boolean(document.querySelector('[aria-label="No intake sessions"]')) &&
          document.body.innerText.includes("Start your first import"),
      ),
    );
    check(
      "home: new-import panel renders (folder mode default, files mode available)",
      await page.evaluate(
        () =>
          Boolean(document.querySelector('section[aria-label="New import"]')) &&
          document.querySelector('[aria-label="Source folder"]')?.getAttribute("aria-checked") === "true" &&
          Boolean(document.querySelector('[aria-label="Source files"]')) &&
          Boolean(document.querySelector('input[aria-label="Folder path"]')),
      ),
    );

    // ------------------------------------------------ start an import
    await setInputValue(page, 'input[aria-label="Folder path"]', FOLDER_A);
    await clickAria(page, "Start import");
    await page.waitForFunction(() => /^\/intake\/.+/.test(window.location.pathname), {
      timeout: 20_000,
    });
    check("create: submitting routes straight to the session details", true, page.url());
    await page.waitForSelector('section[aria-label="Session details"]', { timeout: 20_000 });

    // Live progress: the view polls while queued/running; wait for terminal.
    await page.waitForFunction(
      () => Boolean(document.querySelector('[aria-label="Session status: Completed"]')),
      { timeout: 45_000 },
    );
    check("details: status chip flips to Completed as the pipeline drains", true);
    check(
      "details: progress cards show live counts (4/4, 4 hashed, 4 awaiting review, 0 errors)",
      await page.evaluate(
        () =>
          document.querySelector('[aria-label="Progress card: Items"]')?.textContent.includes("4/4") &&
          document.querySelector('[aria-label="Progress card: Hashed"]')?.textContent.includes("4") &&
          document.querySelector('[aria-label="Progress card: Awaiting review"]')?.textContent.includes("4") &&
          document.querySelector('[aria-label="Progress card: Errors"]')?.textContent.includes("0"),
      ),
    );
    check(
      "details: stage tracker — extract is live (no milestone marker), deferred owners stay named",
      await page.evaluate(() => {
        const tracker = document.querySelector('[aria-label="Pipeline stages"]');
        return (
          Boolean(tracker) &&
          tracker.textContent.includes("Enumerate") &&
          tracker.textContent.includes("Extract") &&
          tracker.textContent.includes("Review") &&
          !tracker.textContent.includes("M3") &&
          tracker.textContent.includes("M5") &&
          tracker.textContent.includes("M9")
        );
      }),
    );
    check(
      "details: extraction rollup card counts real engine output (M2)",
      await page.evaluate(
        () =>
          document
            .querySelector('[aria-label="Progress card: Extracted"]')
            ?.textContent.includes("2") &&
          document
            .querySelector('[aria-label="Progress card: Extracted"]')
            ?.textContent.includes("2 unsupported"),
      ),
    );
    check(
      "details: summary line renders for the completed import",
      await page.evaluate(
        () => (document.querySelector('[aria-label="Session summary"]')?.textContent.length ?? 0) > 0,
      ),
    );

    const rowCount = await page.$$eval('table[aria-label="Session items"] tbody tr', (rows) => rows.length);
    check("details: item table lists the 4 staged files", rowCount === 4, `rows=${rowCount}`);
    check(
      "details: every item carries an Awaiting review chip; junk/hidden files stay out",
      (await page.$$eval('table[aria-label="Session items"] [aria-label="Item status: Awaiting review"]', (els) => els.length)) === 4 &&
        (await page.evaluate(() => document.body.innerText.includes("note.txt"))) &&
        !(await page.evaluate(() => document.body.innerText.includes(".DS_Store"))) &&
        !(await page.evaluate(() => document.body.innerText.includes("secret.txt"))),
    );
    check(
      "details: source path and file count header render",
      await page.evaluate(
        () =>
          document.querySelector('[aria-label="Session source"]')?.textContent.includes("stage: review") &&
          document.body.innerText.includes("Files (4)"),
      ),
    );

    const uiSid = decodeURIComponent(page.url().split("/intake/")[1]);

    // ------------------------------------------------ back to the list
    await clickAria(page, "Back to intake");
    await page.waitForFunction(
      () => Boolean(document.querySelector('[aria-label^="Open session"]')),
      { timeout: 15_000 },
    );
    check(
      "list: completed session renders as a progress card",
      await page.evaluate(
        () =>
          document.querySelector('[aria-label="Intake home"]')?.textContent.includes("4/4 items") &&
          document.querySelector('[aria-label="Intake home"]')?.textContent.includes("Completed"),
      ),
    );

    // ------------------------------------------------ reopen + delete
    await page.evaluate(() => document.querySelector('[aria-label^="Open session"]').click());
    await page.waitForSelector('section[aria-label="Session details"]', { timeout: 20_000 });
    await clickAria(page, "Delete session");
    await page.waitForSelector('[role="alertdialog"]', { timeout: 10_000 });
    check("delete: confirmation dialog explains the staging cleanup", await page.evaluate(
      () => document.querySelector('[role="alertdialog"]')?.textContent.includes("staged copies"),
    ));
    await page.evaluate(() => {
      const dialog = document.querySelector('[role="alertdialog"]');
      const confirm = [...dialog.querySelectorAll("button")].find(
        (button) => button.textContent.trim() === "Delete session",
      );
      confirm?.click();
    });
    await page.waitForFunction(
      () => Boolean(document.querySelector('[aria-label="Session not found"]')),
      { timeout: 15_000 },
    );
    check("delete: view switches to the not-found panel", true);
    const deleted = await getJson(sessionPath(uiSid));
    check("delete: API parity — the session is really gone (404)", deleted.status === 404, String(deleted.status));

    // ------------------------------------------------ cleanliness gates
    check(
      "cleanliness: no failed API call during the whole UI tour",
      failingApi.length === 0,
      failingApi.slice(0, 3).join(" | "),
    );
    check(
      "cleanliness: no console/page errors",
      consoleErrors.length === 0,
      consoleErrors.slice(0, 3).join(" | "),
    );
  } catch (err) {
    check(`fatal: ${err.message}`, false);
    try {
      await page.screenshot({ path: "/tmp/intake-failure.png", fullPage: true });
      fs.writeFileSync("/tmp/intake-failure.txt", await page.content());
    } catch {
      /* ignore */
    }
  } finally {
    await browser.close();
  }
}

// ---------------------------------------------------------------- main
async function main() {
  try {
    await apiPhase();
    await uiPhase();
  } finally {
    // Leave the canonical database and storage root exactly as found.
    for (const sid of [...createdIds]) {
      await deleteSession(sid).catch(() => {});
    }
    const stragglers = await getJson("/intake/sessions?page_size=100").catch(() => null);
    for (const item of stragglers?.body?.items ?? []) {
      await deleteSession(item.id).catch(() => {});
    }
    fs.rmSync(FIX, { recursive: true, force: true });
  }

  const failed = results.filter((entry) => !entry.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  if (failed.length > 0) {
    console.log("FAILURES:");
    for (const entry of failed) console.log(`  - ${entry.name}${entry.extra ? ` — ${entry.extra}` : ""}`);
    process.exitCode = 1;
  }
}

await main();

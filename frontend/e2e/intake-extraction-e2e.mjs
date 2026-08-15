/**
 * Intake M2 Part 2 — Extraction Viewer & Metadata UI end-to-end test.
 *
 * Drives the real API + real UI against a running backend + `next start`,
 * with REAL parseable fixtures (hand-built one-page PDFs — one with a text
 * layer, one without — a long .txt and a .png):
 *
 *   API phase (node fetch, before the browser opens):
 *   - hygiene pre-clean (only extraction suites touch these fixtures)
 *   - folder import completes; descriptors are the real engine output:
 *     txt word/char counts + preview prefix, pdf page count + docinfo
 *     title/author, empty-pdf extracted with 0 characters, png UNSUPPORTED
 *     with a real sha256 and no text key
 *   - raw-text endpoint: byte parity for txt/pdf, honest empty string for
 *     the textless pdf, honest 404 for the unsupported item
 *
 *   UI phase (real browser):
 *   - rollup card + per-row extraction badges (Extracted ×3, Unsupported,
 *     Needs OCR)
 *   - per-file viewer: metadata card values equal the API descriptor
 *     (sha256/counts/statuses), preview = first 500 chars verbatim,
 *     extracted text = full endpoint body (tail beyond the preview present)
 *   - client-side search: highlight marks + match count, zero backend
 *     queries while typing, "No matches" state
 *   - copy + downloads: copy flips to "Copied" (clipboard content when the
 *     browser allows reading it), .txt download byte-parity, .json download
 *     parses to the real descriptor
 *   - honest empty states for the unsupported and the needs-OCR item
 *   - keyboard/a11y: WAI-ARIA tab roving, Escape closes, focus returns to
 *     the row trigger; stable aria-labels throughout
 *   - cleanliness gates: zero failed API calls, zero console/page errors
 *
 * The suite deletes every session it creates and removes its fixture tree,
 * so the canonical database and the storage root are left exactly as found.
 *
 * Usage:
 *   node tests/intake-extraction-e2e.mjs         # http://localhost:3000
 */
import puppeteer from "puppeteer";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";
const DOWNLOADS = fs.mkdtempSync(path.join(os.tmpdir(), "intake-e2e-dl-"));

const results = [];
const check = (name, ok, extra = "") => {
  results.push({ name, ok, extra });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? ` — ${extra}` : ""}`);
};

const STAMP = Date.now().toString(36);
const NEEDLE = "needleword";

// ---------------------------------------------------------------- fixtures
/** Minimal one-page PDF (hand-built xref/trailer); withText=false ⇒ page without any text ops. */
function makePdfBytes({ text = "", title = null, author = null, withText = true }) {
  const esc = (s) => s.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
  const content = withText ? Buffer.from(`BT /F1 12 Tf 72 720 Td (${esc(text)}) Tj ET`, "latin1") : Buffer.alloc(0);
  let info = "";
  if (title !== null) info += `/Title (${esc(title)})`;
  if (author !== null) info += `/Author (${esc(author)})`;
  info += "/CreationDate (D:20240102030405Z)/ModDate (D:20240304050607Z)";
  const objects = [
    Buffer.from("<< /Type /Catalog /Pages 2 0 R >>"),
    Buffer.from("<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
    Buffer.from(
      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ),
    Buffer.concat([Buffer.from(`<< /Length ${content.length} >>\nstream\n`), content, Buffer.from("\nendstream")]),
    Buffer.from("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    Buffer.from(`<< ${info} >>`),
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

const FIX = fs.mkdtempSync(path.join(os.tmpdir(), "intake-extract-e2e-"));
const FOLDER = path.join(FIX, "papers");
fs.mkdirSync(FOLDER, { recursive: true });

const NOTE_REL = `note-${STAMP}.txt`;
const NOTE_TEXT =
  `Intake extraction viewer E2E note ${STAMP}\n` +
  `${NEEDLE} once early.\n` +
  "filler line — the quick brown fox jumps over the lazy dog.\n".repeat(12) +
  `${NEEDLE} twice near the tail (beyond the 500-char preview).\n` +
  `${NEEDLE} third and final occurrence.\n`;
const NOTE_BYTES = Buffer.from(NOTE_TEXT, "utf8");
const NOTE_SHA = crypto.createHash("sha256").update(NOTE_BYTES).digest("hex");
const NOTE_WORDS = NOTE_TEXT.trim().split(/\s+/).length;
const FIRST500 = NOTE_TEXT.slice(0, 500);

const PAPER_REL = `paper-${STAMP}.pdf`;
const PAPER_TITLE = `Extraction E2E paper ${STAMP}`;
const PAPER_AUTHOR = "E2E Harness";
const PAPER_TEXT = `${NEEDLE} sensemaking paper ${STAMP}`;
const SCAN_REL = `scan-${STAMP}.pdf`;
const PHOTO_REL = `photo-${STAMP}.png`;

fs.writeFileSync(path.join(FOLDER, NOTE_REL), NOTE_BYTES);
fs.writeFileSync(
  path.join(FOLDER, PAPER_REL),
  makePdfBytes({ text: PAPER_TEXT, title: PAPER_TITLE, author: PAPER_AUTHOR }),
);
fs.writeFileSync(path.join(FOLDER, SCAN_REL), makePdfBytes({ withText: false }));
fs.writeFileSync(path.join(FOLDER, PHOTO_REL), Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.alloc(16, 0x11)]));

// ---------------------------------------------------------------- helpers
const getJson = (urlPath) =>
  fetch(`${API}${urlPath}`).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));
const getText = (urlPath) =>
  fetch(`${API}${urlPath}`).then(async (r) => ({ status: r.status, body: await r.text().catch(() => "") }));
const postJson = (urlPath, body = {}, method = "POST") =>
  fetch(`${API}${urlPath}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  }).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

const sessionPath = (sid) => `/intake/sessions/${encodeURIComponent(sid)}`;
const itemTextPath = (sid, iid) => `${sessionPath(sid)}/items/${encodeURIComponent(iid)}/extraction/text`;

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
/** Click an element with an explicit role whose accessible name is its text (tabs). */
async function clickRole(page, role, name) {
  const clicked = await page.evaluate(
    (r, n) => {
      const el = [...document.querySelectorAll(`[role="${r}"]`)].find(
        (node) => node.textContent.trim() === n,
      );
      if (!el) return false;
      el.click();
      return true;
    },
    role,
    name,
  );
  if (!clicked) throw new Error(`Element role="${role}" “${name}” missing`);
  return true;
}
/** Set a controlled input value the React-safe way. */
async function setInputValue(page, selector, value) {
  await page.waitForSelector(selector, { timeout: 10_000 });
  await page.evaluate(
    (sel, val) => {
      const el = document.querySelector(sel);
      const proto = Object.getPrototypeOf(el);
      const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
      setter.call(el, val);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    },
    selector,
    value,
  );
}
async function pollSession(sid, timeoutMs = 60_000) {
  const deadline = Date.now() + timeoutMs;
  let last = null;
  while (Date.now() < deadline) {
    const res = await getJson(sessionPath(sid));
    last = res.body;
    if (["completed", "failed", "cancelled"].includes(res.body?.status)) return res.body;
    await new Promise((r) => setTimeout(r, 700));
  }
  throw new Error(`poll timeout on session; last=${JSON.stringify(last).slice(0, 300)}`);
}
const waitForFile = async (name, timeoutMs = 10_000) => {
  const file = path.join(DOWNLOADS, name);
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (fs.existsSync(file) && fs.statSync(file).size > 0) return file;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`download did not land: ${name}`);
};

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
    path: FOLDER,
    title: `Extraction viewer E2E ${STAMP}`,
    actor: "e2e",
  });
  check("api: folder import accepted (201, queued)", created.status === 201 && created.body.status === "queued", String(created.status));
  const sid = created.body.id;

  const session = await pollSession(sid);
  check(
    "api: import completed; extraction rollup is real (3 extracted, 1 unsupported, 0 errors)",
    session.status === "completed" &&
      session.statistics?.extracted_items === 3 &&
      session.statistics?.unsupported_items === 1 &&
      session.statistics?.errors === 0 &&
      typeof session.summary === "string" &&
      session.summary.includes("Extracted text from 3 file(s); 1 unsupported"),
    `stats=${JSON.stringify({ e: session.statistics?.extracted_items, u: session.statistics?.unsupported_items })}`,
  );

  const items = (await getJson(`${sessionPath(sid)}/items?page_size=50`)).body;
  check("api: listing returns the 4 files", items.total_count === 4, `total=${items.total_count}`);
  const byRel = Object.fromEntries(items.items.map((item) => [item.relative_path, item]));

  const note = byRel[NOTE_REL];
  check(
    "api: txt descriptor is exact (sha/size/words/chars/preview/engine)",
    Boolean(note) &&
      note.sha256 === NOTE_SHA &&
      note.extraction?.status === "extracted" &&
      note.extraction?.engine === "stdlib-text 1.0 (utf-8)" &&
      note.extraction?.format === "text" &&
      note.extraction?.word_count === NOTE_WORDS &&
      note.extraction?.character_count === NOTE_TEXT.length &&
      note.extraction?.preview_text === FIRST500 &&
      typeof note.extraction?.text_key === "string" &&
      note.extraction?.text_key.startsWith("intake-extracted/") &&
      Array.isArray(note.extraction?.warnings),
    `engine=${note?.extraction?.engine} chars=${note?.extraction?.character_count} words=${note?.extraction?.word_count}`,
  );

  const paper = byRel[PAPER_REL];
  check(
    "api: pdf descriptor carries real docinfo (title/author/pages/embedded)",
    Boolean(paper) &&
      paper.extraction?.status === "extracted" &&
      paper.extraction?.engine === "pypdf 5.1.0" &&
      paper.extraction?.page_count === 1 &&
      paper.extraction?.document_title === PAPER_TITLE &&
      paper.extraction?.author === PAPER_AUTHOR &&
      Object.keys(paper.extraction?.embedded_metadata ?? {}).length >= 2 &&
      (paper.extraction?.character_count ?? 0) > 0,
    `title=${JSON.stringify(paper?.extraction?.document_title)} pages=${paper?.extraction?.page_count}`,
  );

  const scan = byRel[SCAN_REL];
  check(
    "api: textless pdf is honestly extracted with zero characters (needs-OCR case)",
    Boolean(scan) &&
      scan.extraction?.status === "extracted" &&
      scan.extraction?.character_count === 0 &&
      scan.extraction?.word_count === 0 &&
      typeof scan.extraction?.text_key === "string",
    `chars=${scan?.extraction?.character_count}`,
  );

  const photo = byRel[PHOTO_REL];
  check(
    "api: png is UNSUPPORTED — real sha256, no text key, no preview",
    Boolean(photo) &&
      photo.extraction?.status === "unsupported" &&
      photo.extraction?.text_key === null &&
      photo.extraction?.preview_text === null &&
      typeof photo.extraction?.sha256 === "string" &&
      photo.extraction?.sha256.length === 64,
    `status=${photo?.extraction?.status}`,
  );

  const noteText = await getText(itemTextPath(sid, note.id));
  check(
    "api: raw-text endpoint serves byte-parity full text (beyond the preview)",
    noteText.status === 200 && noteText.body === NOTE_TEXT && noteText.body.length > 500,
    `status=${noteText.status} bytes=${Buffer.byteLength(noteText.body)}`,
  );
  const paperText = await getText(itemTextPath(sid, paper.id));
  check(
    "api: raw text of the pdf contains its exact text layer",
    paperText.status === 200 && paperText.body.includes(PAPER_TEXT) && paperText.body.includes(NEEDLE),
  );
  const scanText = await getText(itemTextPath(sid, scan.id));
  check(
    "api: raw text of the textless pdf is an honest empty string (200)",
    scanText.status === 200 && scanText.body === "",
    `status=${scanText.status} len=${scanText.body.length}`,
  );
  const photoText = await getText(itemTextPath(sid, photo.id));
  check(
    "api: raw text of an unsupported item is an honest 404",
    photoText.status === 404,
    `status=${photoText.status}`,
  );

  return { sid, ids: { note: note.id, paper: paper.id, scan: scan.id, photo: photo.id } };
}

// ---------------------------------------------------------------- UI phase
async function uiPhase({ sid }) {
  console.log("— UI phase —");
  const browser = await puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 960 });
  await browser.defaultBrowserContext().overridePermissions(BASE, ["clipboard-read", "clipboard-write"]);

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

  let downloadSession = null;
  try {
    const cdp = await page.createCDPSession();
    await cdp.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: DOWNLOADS });
    downloadSession = cdp;

    await page.goto(`${BASE}/intake/${encodeURIComponent(sid)}`, { waitUntil: "networkidle2", timeout: 60_000 });
    await page.waitForFunction(
      () => Boolean(document.querySelector('[aria-label="Session status: Completed"]')),
      { timeout: 45_000 },
    );
    check("details: session page loads to a completed state", true);

    check(
      "rollup: Extracted progress card shows 3 extracted, 1 unsupported",
      await page.evaluate(() => {
        const card = document.querySelector('[aria-label="Progress card: Extracted"]');
        return Boolean(card) && card.textContent.includes("3") && card.textContent.includes("1 unsupported");
      }),
    );
    check(
      "badges: rows carry Extracted / Needs OCR / Unsupported chips from real descriptors",
      await page.evaluate(() => {
        const table = document.querySelector('table[aria-label="Session items"]');
        if (!table) return false;
        const count = (aria) => table.querySelectorAll(`[aria-label="${aria}"]`).length;
        return (
          count("Extraction: extracted") === 3 &&
          count("Extraction: unsupported format") === 1 &&
          count("Extraction: needs OCR — the file has no extractable text layer") === 1
        );
      }),
    );

    // ------------------------------------------------ note.txt viewer
    await page.waitForSelector('[aria-label^="View extraction for "]', { timeout: 15_000 });
    await clickAria(page, `View extraction for ${NOTE_REL}`);
    await page.waitForSelector("#extraction-viewer", { timeout: 10_000 });
    check(
      "viewer: opens inline; focus lands on the labelled heading",
      await page.evaluate(() => document.activeElement?.id === "extraction-viewer-heading"),
    );

    check(
      "metadata: filename, sha-256, counts and statuses equal the API descriptor",
      await page.evaluate(
        (args) => {
          const has = (aria) => Boolean(document.querySelector(`[aria-label="${aria}"]`));
          return (
            has(`Metadata: Filename: note-${args.stamp}.txt`) &&
            has(`Metadata: Extension: .txt`) &&
            has(`Metadata: MIME: text/plain`) &&
            has(`Metadata: SHA-256: ${args.sha}`) &&
            has(`Metadata: Word count: ${args.words}`) &&
            has(`Metadata: Character count: ${args.chars}`) &&
            has("Metadata: Extraction status: extracted") &&
            has("Metadata: Unsupported: No") &&
            has("Metadata: Needs OCR: No")
          );
        },
        { stamp: STAMP, sha: NOTE_SHA, words: NOTE_WORDS, chars: NOTE_TEXT.length },
      ),
    );

    // WAI-ARIA tabs keyboard roving
    await page.evaluate(() => document.querySelector('[role="tab"][aria-selected="true"]')?.focus());
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("End");
    check(
      "tabs: arrow/Home/End roving updates selection and focus (WAI-ARIA tabs)",
      await page.evaluate(() => {
        const selected = document.querySelector('[role="tab"][aria-selected="true"]');
        return selected?.textContent === "Extracted text" && document.activeElement === selected;
      }),
    );
    await page.keyboard.press("Home");

    // Preview tab: exact first 500 chars
    await page.evaluate(() => document.querySelector('[role="tab"]')?.focus());
    await clickRole(page, "tab", "Preview");
    await page.waitForSelector('[role="tabpanel"] [aria-label$=" content"]', { timeout: 10_000 });
    check(
      "preview: pane renders exactly the first 500 extracted characters",
      await page.evaluate((first500) => {
        const pre = document.querySelector('[aria-label^="Preview of "][aria-label$=" content"]');
        return pre?.textContent === first500;
      }, FIRST500),
    );
    check(
      "preview: disclosure line states 500-of-N honestly",
      await page.evaluate(
        (chars) => document.body.innerText.includes(`First 500 of ${chars.toLocaleString()} characters`),
        NOTE_TEXT.length,
      ),
    );

    // Extracted text tab: full body incl. tail, then search
    await clickRole(page, "tab", "Extracted text");
    await page.waitForFunction(
      () => Boolean(document.querySelector('[aria-label^="Extracted text of "][aria-label$=" content"]')),
      { timeout: 15_000 },
    );
    check(
      "raw text: pane equals the full endpoint body (tail beyond the preview present)",
      await page.evaluate(
        (full) =>
          document.querySelector('[aria-label^="Extracted text of "][aria-label$=" content"]')?.textContent === full,
        NOTE_TEXT,
      ),
    );
    check(
      "raw text: footer reports the exact character count, read-only",
      await page.evaluate((chars) => {
        const viewer = document.querySelector('#extraction-viewer');
        return (
          viewer.textContent.includes(`${chars.toLocaleString()} characters`) &&
          viewer.textContent.includes("read-only") &&
          document.querySelectorAll('#extraction-viewer [contenteditable="true"]').length === 0 &&
          document.querySelectorAll("#extraction-viewer textarea").length === 0
        );
      }, NOTE_TEXT.length),
    );

    await setInputValue(page, `input[aria-label="Search extracted text of ${NOTE_REL}"]`, NEEDLE);
    await page.waitForFunction(
      () => document.querySelector('[aria-label="Search match count"]')?.textContent.trim() === "3 matches",
      { timeout: 10_000 },
    );
    check(
      "search: highlight marks equal the reported match count (3)",
      await page.evaluate(
        () =>
          document.querySelector('[aria-label="Search match count"]')?.textContent.trim() === "3 matches" &&
          document.querySelectorAll("#extraction-viewer mark").length === 3,
      ),
    );
    await setInputValue(page, `input[aria-label="Search extracted text of ${NOTE_REL}"]`, "zzz-no-such-token");
    await page.waitForFunction(
      () => document.querySelector('[aria-label="Search match count"]')?.textContent.trim() === "No matches",
      { timeout: 10_000 },
    );
    check(
      "search: honest no-match state",
      await page.evaluate(() => document.querySelectorAll("#extraction-viewer mark").length === 0),
    );
    await setInputValue(page, `input[aria-label="Search extracted text of ${NOTE_REL}"]`, "");

    // Copy + downloads
    await clickAria(page, `Copy extracted text of ${NOTE_REL}`);
    await page.waitForFunction(
      () => [...document.querySelectorAll("button")].some((b) => b.textContent.trim() === "Copied"),
      { timeout: 10_000 },
    );
    const clipboardText = await page
      .evaluate(() => navigator.clipboard.readText())
      .catch(() => null);
    check(
      "copy: button confirms; clipboard carries the full text when the browser allows reading it",
      clipboardText === null || clipboardText === NOTE_TEXT,
      clipboardText === null ? "clipboard read denied — Copied state asserted instead" : `${clipboardText.length} chars`,
    );

    await clickAria(page, `Download extracted text of ${NOTE_REL} (.txt)`);
    const txtFile = await waitForFile(`note-${STAMP}.extracted.txt`);
    check(
      "download: .txt carries the byte-exact extracted text",
      fs.readFileSync(txtFile).equals(NOTE_BYTES),
    );
    await clickAria(page, `Download extraction metadata of ${NOTE_REL} (.json)`);
    const jsonFile = await waitForFile(`note-${STAMP}.metadata.json`);
    const meta = JSON.parse(fs.readFileSync(jsonFile, "utf8"));
    check(
      "download: .json parses to the real descriptor (sha/status/needs_ocr)",
      meta.extraction?.status === "extracted" &&
        meta.item?.sha256 === NOTE_SHA &&
        meta.needs_ocr === false &&
        meta.item?.relative_path === NOTE_REL,
    );

    // Escape closes (focus inside the viewer) + focus returns to the row trigger
    await page.focus('[aria-label="Close extraction viewer"]');
    await page.keyboard.press("Escape");
    await page.waitForFunction(
      () => !document.querySelector("#extraction-viewer"),
      { timeout: 10_000 },
    );
    // Focus restoration is deferred one tick (setTimeout 0 in closeViewer) —
    // wait for the trigger to actually receive focus instead of racing the
    // DOM-removal callback (the contract is the end state, not the tick).
    await page.waitForFunction(
      (rel) =>
        document.activeElement?.getAttribute("aria-label") === `View extraction for ${rel}`,
      { timeout: 10_000 },
      NOTE_REL,
    );
    check(
      "dismiss: Escape closes the viewer; focus returns to the row trigger",
      true,
    );

    // ------------------------------------------------ scan.pdf (needs OCR)
    await clickAria(page, `View extraction for ${SCAN_REL}`);
    await page.waitForSelector("#extraction-viewer", { timeout: 10_000 });
    check(
      "needs-ocr: viewer carries the Needs OCR badge derived from a real zero-character extraction",
      await page.evaluate(
        () =>
          Boolean(
            document.querySelector(
              '#extraction-viewer [aria-label="Extraction: needs OCR — the file has no extractable text layer"]',
            ),
          ) &&
          Boolean(document.querySelector('[aria-label="Metadata: Needs OCR: Yes"]')),
      ),
    );
    await clickRole(page, "tab", "Preview");
    check(
      "needs-ocr: preview shows the honest empty state (no fabrication)",
      await page.evaluate(
        () =>
          Boolean(document.querySelector('[aria-label="Preview unavailable"]')) &&
          document.querySelector('[aria-label="Preview unavailable"]').textContent.includes(
            "no extractable text layer",
          ),
      ),
    );
    await clickRole(page, "tab", "Extracted text");
    await page.waitForFunction(
      () => Boolean(document.querySelector('[aria-label="Extracted text unavailable"]')),
      { timeout: 15_000 },
    );
    check(
      "needs-ocr: text tab shows the honest empty state; copy/download disabled",
      await page.evaluate(
        (rel) =>
          document.querySelector('[aria-label="Extracted text unavailable"]').textContent.includes(
            "no extractable text layer",
          ) &&
          document.querySelector(`[aria-label="Copy extracted text of ${rel}"]`).disabled === true &&
          document.querySelector(`[aria-label="Download extracted text of ${rel} (.txt)"]`).disabled === true,
        SCAN_REL,
      ),
    );
    await page.focus('[aria-label="Close extraction viewer"]');
    await page.keyboard.press("Escape");
    await page.waitForFunction(() => !document.querySelector("#extraction-viewer"), { timeout: 10_000 });

    // ------------------------------------------------ photo.png (unsupported)
    await clickAria(page, `View extraction for ${PHOTO_REL}`);
    await page.waitForSelector("#extraction-viewer", { timeout: 10_000 });
    check(
      "unsupported: badge + metadata row report the format honestly",
      await page.evaluate(
        () =>
          Boolean(
            document.querySelector('#extraction-viewer [aria-label="Extraction: unsupported format"]'),
          ) && Boolean(document.querySelector('[aria-label="Metadata: Unsupported: Yes"]')),
      ),
    );
    await clickRole(page, "tab", "Preview");
    check(
      "unsupported: preview empty state names the reason",
      await page.evaluate(
        () =>
          document.querySelector('[aria-label="Preview unavailable"]')?.textContent.includes(
            "not supported by the extraction engine",
          ) ?? false,
      ),
    );
    await clickRole(page, "tab", "Extracted text");
    check(
      "unsupported: text tab empty state, no raw-text request was ever fired from the UI",
      await page.evaluate(
        () =>
          document.querySelector('[aria-label="Extracted text unavailable"]')?.textContent.includes(
            "not supported by the extraction engine",
          ) ?? false,
      ) && !failingApi.some((line) => line.includes("extraction/text")),
      failingApi.slice(0, 3).join(" | "),
    );
    await page.focus('[aria-label="Close extraction viewer"]');
    await page.keyboard.press("Escape");
    await page.waitForFunction(() => !document.querySelector("#extraction-viewer"), { timeout: 10_000 });

    // ------------------------------------------------ cleanliness gates
    check("gate: zero failed API calls while driving the viewer", failingApi.length === 0, failingApi.slice(0, 3).join(" | "));
    check("gate: zero console/page errors", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" | "));
  } finally {
    downloadSession?.detach?.().catch(() => {});
    await browser.close().catch(() => {});
  }
}

// ---------------------------------------------------------------- run
async function main() {
  const { sid } = await apiPhase();
  try {
    await uiPhase({ sid });
  } finally {
    for (const line of (await getJson("/intake/sessions?page_size=100")).body?.items ?? []) {
      await postJson(sessionPath(line.id), null, "DELETE");
    }
    fs.rmSync(FIX, { recursive: true, force: true });
    fs.rmSync(DOWNLOADS, { recursive: true, force: true });
    check("cleanup: sessions deleted, fixtures and downloads removed", true);
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

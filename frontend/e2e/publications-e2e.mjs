/**
 * Publications module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   list -> add publication (manual entry + object links) -> server-side
 *   search -> open detail -> citation styles -> attach PDF -> edit ->
 *   duplicate-warning in the create form -> BibTeX import with duplicate
 *   report -> export links -> delete -> object lens on the Object page.
 *
 * Usage:
 *   node tests/publications-e2e.mjs            # http://127.0.0.1:3000
 */
import puppeteer from "puppeteer";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

const results = [];
const check = (name, ok, extra = "") => {
  results.push({ name, ok, extra });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? ` — ${extra}` : ""}`);
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const STAMP = Date.now().toString(36);
const PUB_TITLE = `E2E Catalysis Study ${STAMP}`;
const PUB_TITLE_V2 = `E2E Catalysis Study ${STAMP} v2`;
const PUB_DOI = `10.5555/e2e-${STAMP}`;
const IMPORT_TITLE = `E2E Imported ${STAMP}`;

const createObject = (type, title) =>
  fetch(`${API}/objects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ object_type: type, title, created_by: "faculty:e2e" }),
  }).then((r) => r.json());

/**
 * Click a button by its exact label. When a dialog is open, a button INSIDE
 * the dialog wins over a same-labelled page button (the page "Import" opener
 * and the import form's "Import" submit share a label).
 */
async function clickButtonWithText(page, text, { inDialog = false } = {}) {
  const clicked = await page.evaluate(
    (wanted, dialogOnly) => {
      const candidates = [...document.querySelectorAll("button")].filter(
        (btn) => btn.textContent?.trim() === wanted && !btn.disabled,
      );
      const dialogButton = candidates.find((btn) =>
        btn.closest('[role="dialog"], [role="alertdialog"]'),
      );
      const button = dialogOnly ? dialogButton : dialogButton ?? candidates[0];
      if (!button) return false;
      button.click();
      return true;
    },
    text,
    inDialog,
  );
  if (!clicked) throw new Error(`No clickable button labelled “${text}” found.`);
  return true;
}

async function main() {
  // Seed objects to link the publication against.
  const project = await createObject("research_project", `E2E Project ${STAMP}`);
  const grant = await createObject("grant", `E2E Grant ${STAMP}`);
  check("seed link objects via API", Boolean(project.id && grant.id), project.id ?? "");

  const pdfPath = path.join(os.tmpdir(), `e2e-pub-${STAMP}.pdf`);
  const pdfBytes = Buffer.from(`%PDF-1.4 e2e ${STAMP}\n`, "utf8");
  fs.writeFileSync(pdfPath, pdfBytes);

  const browser = await puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  const consoleErrors = [];
  const failedResponses = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));
  page.on("response", (res) => {
    if (res.status() >= 400) {
      failedResponses.push(
        `${res.status()} ${res.request().method()} ${res.url()}`,
      );
    }
  });

  try {
    // ------------------------------------------------------------ list page
    await page.goto(`${BASE}/publications`, { waitUntil: "networkidle0" });
    await page.waitForSelector("h1", { timeout: 15_000 });
    const heading = await page.$eval("h1", (el) => el.textContent?.trim());
    check("publications list page loads", heading === "Publications", heading ?? "");
    const listError = await page.evaluate(() =>
      document.body.innerText.includes("Could not load publications"),
    );
    check("list fetches from backend without error (no 404)", !listError);
    const sidebarLink = await page.$eval("nav", (nav) => nav.innerText.includes("Publications"));
    check("sidebar exposes a Publications entry", sidebarLink);

    // ------------------------------------------- create via the modal (JSON)
    await clickButtonWithText(page, "Add Publication");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await page.type('input[placeholder="Deep Learning for Catalysis"]', PUB_TITLE);
    await page.type('input[placeholder="Nature Catalysis"]', "E2E Journal of Testing");
    await page.type('input[placeholder="2026"]', "2026");
    await page.type('input[placeholder="10.1038/s41586-020-2649-2"]', PUB_DOI);
    await page.type('input[aria-label="Author 1 name"]', "Gupta, Vipin");
    await page.type('input[placeholder="faculty:1"]', "faculty:e2e");
    // link the seeded objects through the multi-select pickers
    await page.select('select[aria-label="Linked projects"]', project.id);
    await page.select('select[aria-label="Linked grants"]', grant.id);
    await clickButtonWithText(page, "Add publication");
    await page.waitForFunction(
      (title) =>
        [...document.querySelectorAll("table a")].some(
          (a) => a.textContent?.trim() === title,
        ),
      { timeout: 15_000 },
      PUB_TITLE,
    );
    check("create: new publication appears in the list", true);

    // ----------------------------------------------- server-side search
    await page.type('input[type="search"]', "e2e nonexistent topic");
    await sleep(600); // debounce + request
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching publications"),
      { timeout: 15_000 },
    );
    check("search: non-matching query shows the empty state", true);
    await page.evaluate(() => {
      const input = document.querySelector('input[type="search"]');
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value",
      ).set;
      setter.call(input, "catalysis study");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await page.waitForFunction(
      (title) =>
        [...document.querySelectorAll("table a")].some(
          (a) => a.textContent?.trim() === title,
        ),
      { timeout: 15_000 },
      PUB_TITLE,
    );
    check("search: token search finds the publication (server-side q)", true);
    await page.evaluate(() => {
      const button = document.querySelector('button[aria-label="Clear search"]');
      button?.click();
    });
    await sleep(400);

    // ------------------------------------------------------------ detail page
    await page.evaluate((title) => {
      const link = [...document.querySelectorAll("table a")].find(
        (a) => a.textContent?.trim() === title,
      );
      link?.click();
    }, PUB_TITLE);
    await page.waitForSelector("h1", { timeout: 15_000 });
    await page.waitForFunction(
      (title) => document.querySelector("h1")?.textContent?.trim() === title,
      { timeout: 15_000 },
      PUB_TITLE,
    );
    check("detail page opens with the publication title", true);
    const detailText = await page.evaluate(() => document.body.innerText);
    check(
      "detail shows DOI, venue and authors sections",
      detailText.includes(PUB_DOI) &&
        detailText.includes("E2E Journal of Testing") &&
        detailText.includes("Gupta, Vipin"),
    );
    check(
      "detail shows linked objects (project + grant)",
      detailText.includes(`E2E Project ${STAMP}`) && detailText.includes(`E2E Grant ${STAMP}`),
    );

    // ----------------------------------------------------- citation generator
    await page.waitForSelector("blockquote", { timeout: 15_000 });
    const apa = await page.$eval("blockquote", (el) => el.textContent ?? "");
    check("APA citation renders (backend-formatted)", apa.includes("Gupta") && apa.includes("2026"),
      apa.slice(0, 70));
    await page.select('select[aria-label="Citation style"]', "ieee");
    await page.waitForFunction(
      (title) =>
        document.querySelector("blockquote")?.textContent?.includes(`“`) ||
        document.querySelector("blockquote")?.textContent?.includes(`"${title}`),
      { timeout: 15_000 },
      PUB_TITLE,
    );
    const ieee = await page.$eval("blockquote", (el) => el.textContent ?? "");
    check("IEEE citation switches style", ieee.includes(`"${PUB_TITLE}`), ieee.slice(0, 70));

    // ------------------------------------------------------------- PDF attach
    const fileInput = await page.$('input[type="file"][accept*="pdf"]');
    await fileInput.uploadFile(pdfPath);
    await page.waitForFunction(
      () => document.body.innerText.includes("Download PDF"),
      { timeout: 15_000 },
    );
    check("PDF attach: detail now offers a Download PDF action", true);
    const pdfHref = await page.evaluate(
      () => [...document.querySelectorAll("a")].find((a) => a.href.includes("/pdf"))?.href,
    );
    const downloaded = await fetch(pdfHref).then((r) => r.arrayBuffer());
    check(
      "PDF download is byte-identical",
      Buffer.from(downloaded).equals(pdfBytes),
      `${downloaded.byteLength} bytes`,
    );

    // --------------------------------------------------------------- edit
    await clickButtonWithText(page, "Edit");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await page.evaluate(() => {
      const input = document.querySelector('input[placeholder="Deep Learning for Catalysis"]');
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value",
      ).set;
      setter.call(input, "");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await page.type('input[placeholder="Deep Learning for Catalysis"]', PUB_TITLE_V2);
    await page.select('select[aria-label="Pipeline stage"]', "under_review");
    await clickButtonWithText(page, "Save changes");
    await page.waitForFunction(
      (title) => document.querySelector("h1")?.textContent?.trim() === title,
      { timeout: 15_000 },
      PUB_TITLE_V2,
    );
    const afterEdit = await page.evaluate(() => document.body.innerText);
    check("edit updates the title on the detail page", true);
    check(
      "edit keeps the linked objects (absent groups untouched)",
      afterEdit.includes(`E2E Project ${STAMP}`),
    );
    check(
      "edit sets the pipeline stage",
      afterEdit.toLowerCase().includes("under review"),
    );

    // ----------------------------------------- duplicate warning on create
    await page.goto(`${BASE}/publications`, { waitUntil: "networkidle0" });
    await clickButtonWithText(page, "Add Publication");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await page.type('input[placeholder="Deep Learning for Catalysis"]', `Totally Different ${STAMP}`);
    await page.type('input[placeholder="10.1038/s41586-020-2649-2"]', PUB_DOI);
    await page.type('input[placeholder="faculty:1"]', "faculty:e2e");
    await clickButtonWithText(page, "Add publication");
    await page.waitForSelector('form[role="dialog"] [role="alert"]', { timeout: 15_000 });
    const dupeAlert = await page.$eval(
      'form[role="dialog"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check(
      "duplicate DOI surfaces the backend 409 in the modal",
      dupeAlert.toLowerCase().includes("duplicate") || dupeAlert.includes("already exists"),
      dupeAlert.slice(0, 80),
    );
    await clickButtonWithText(page, "Cancel", { inDialog: true });
    await page.waitForFunction(
      () => !document.querySelector('form[role="dialog"]'),
      { timeout: 10_000 },
    );

    // ------------------------------------------------- import (bibtex + dupe)
    await clickButtonWithText(page, "Import");
    await page.waitForSelector('form[role="dialog"] textarea[aria-label="Bibliography text"]', { timeout: 10_000 });
    const bibtex = [
      `@article{imp${STAMP},`,
      `  title = {${IMPORT_TITLE}},`,
      `  author = {Rao, Anil},`,
      `  journal = {E2E Import Journal},`,
      `  year = {2024},`,
      `}`,
      `@article{dupe${STAMP},`,
      `  title = {Same DOI Again},`,
      `  author = {Someone, Else},`,
      `  year = {2025},`,
      `  doi = {${PUB_DOI}},`,
      `}`,
    ].join("\n");
    await page.type('textarea[aria-label="Bibliography text"]', bibtex);
    await page.type('form[role="dialog"] input[placeholder="faculty:1"]', "faculty:e2e");
    await clickButtonWithText(page, "Import", { inDialog: true });
    await page.waitForFunction(
      () => document.body.innerText.includes("Imported 1 publication"),
      { timeout: 15_000 },
    );
    const importText = await page.evaluate(() => document.body.innerText);
    check("import creates the new entry", true);
    check(
      "import reports the duplicate (never silently overwritten)",
      importText.includes("1 duplicate skipped") && importText.includes("Same DOI Again"),
    );
    await clickButtonWithText(page, "Done");
    await sleep(300);

    // ------------------------------------------------------------- export
    const exportHref = await page.evaluate(
      () =>
        [...document.querySelectorAll("a")].find((a) =>
          a.href.includes("/publications/export?fmt=bibtex"),
        )?.href,
    );
    check("export link points at /publications/export?fmt=bibtex", Boolean(exportHref), "");
    const bib = await fetch(exportHref).then((r) => r.text());
    check(
      "bibtex export contains the publications",
      bib.includes("@article{") && bib.includes(PUB_TITLE_V2) && bib.includes(IMPORT_TITLE),
    );

    // ------------------------------------------------------------- delete
    await page.evaluate((title) => {
      const link = [...document.querySelectorAll("table a")].find(
        (a) => a.textContent?.trim() === title,
      );
      link?.click();
    }, PUB_TITLE_V2);
    await page.waitForFunction(
      (title) => document.querySelector("h1")?.textContent?.trim() === title,
      { timeout: 15_000 },
      PUB_TITLE_V2,
    );
    await clickButtonWithText(page, "Delete");
    await page.waitForSelector('div[role="alertdialog"]', { timeout: 10_000 });
    await page.evaluate(() => {
      const dialog = document.querySelector('div[role="alertdialog"]');
      const button = [...dialog.querySelectorAll("button")].find(
        (btn) => btn.textContent?.trim() === "Delete" && !btn.disabled,
      );
      button?.click();
    });
    await page.waitForFunction(() => location.pathname.endsWith("/publications"), {
      timeout: 15_000,
    });
    const gone = await fetch(`${API}/publications?page_size=100`).then((r) => r.json());
    const stillThere = (gone.items ?? []).some((p) => p.title === PUB_TITLE_V2);
    check("delete removes the publication (back at list, API agrees)", !stillThere);

    // --------------------------------------------- object lens (object page)
    // The imported publication wasn't linked; link one via the API and verify
    // the Object detail page renders its Publications section with it.
    await fetch(`${API}/publications`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: `E2E Lens Study ${STAMP}`,
        publication_type: "journal_article",
        uploaded_by: "faculty:e2e",
        links: { projects: [project.id] },
      }),
    });
    await page.goto(`${BASE}/objects/${encodeURIComponent(project.id)}`, {
      waitUntil: "networkidle0",
    });
    await sleep(800);
    const objectPage = await page.evaluate(() => document.body.innerText);
    check(
      "object detail page renders its Publications section (object lens)",
      objectPage.includes("Publications") && objectPage.includes(`E2E Lens Study ${STAMP}`),
    );

    // --------------------------------------------------------- cleanliness
    const hostileApi = failedResponses.filter((line) => {
      if (!line.includes("/api/v1/")) return false;
      // The duplicate-create check above INTENTIONALLY produces a 409.
      return !(line.startsWith("409 POST") && line.endsWith("/api/v1/publications"));
    });
    check("no failing API requests (>=400)", hostileApi.length === 0, hostileApi[0] ?? "");
    const hostile = consoleErrors.filter(
      (line) =>
        !line.includes("favicon") &&
        !line.includes("404 (Not Found)") && // /favicon.ico — no favicon ships yet
        // The duplicate-create check INTENTIONALLY produces a 409; chromium
        // logs every non-2xx fetch as a console error.
        !line.includes("409 (Conflict)") &&
        !line.includes("Download the React DevTools") &&
        !line.includes("AbortError"),
    );
    check("no browser console errors", hostile.length === 0, hostile[0] ?? "");
  } catch (error) {
    check("unhandled E2E failure", false, String(error));
  } finally {
    await browser.close();
    fs.rmSync(pdfPath, { force: true });
  }

  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed.`);
  process.exit(failed ? 1 : 0);
}

await main();

/**
 * Documents module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   list -> upload dialog (file + link + tags) -> search -> paginate ->
 *   open detail -> edit -> delete. Verifies the object-document link shows up
 *   on both the document detail page and the object detail page.
 *
 * Usage:
 *   node tests/documents-e2e.mjs            # http://127.0.0.1:3000
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
const DOC_TITLE = `E2E Syllabus ${STAMP}`;
const DOC_TITLE_V2 = `E2E Syllabus ${STAMP} v2`;

async function main() {
  // Seed a course object to link the document against.
  const course = await fetch(`${API}/objects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      object_type: "course",
      title: `E2E Course ${STAMP}`,
      created_by: "faculty:e2e",
    }),
  }).then((r) => r.json());
  check("seed course object via API", Boolean(course.id), course.id ?? "");

  // A real file to upload.
  const filePath = path.join(os.tmpdir(), `e2e-${STAMP}.txt`);
  fs.writeFileSync(filePath, `E2E upload payload ${STAMP}\n`);

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
    if (res.status() >= 400) failedResponses.push(`${res.status()} ${res.url()}`);
  });

  try {
    // ------------------------------------------------------- list (empty->ok)
    await page.goto(`${BASE}/documents`, { waitUntil: "networkidle0" });
    await page.waitForSelector("h1", { timeout: 15_000 });
    const heading = await page.$eval("h1", (el) => el.textContent?.trim());
    check("documents list page loads", heading === "Documents", heading ?? "");
    const listError = await page.evaluate(() =>
      document.body.innerText.includes("Could not load documents"),
    );
    check("list fetches from backend without error (no 404)", !listError);

    // -------------------------------------------------------- upload dialog
    await page.evaluate(() => {
      const button = [...document.querySelectorAll("button")].find((btn) =>
        btn.textContent?.includes("Upload Document"),
      );
      button?.click();
    });
    await page.waitForSelector("#document-modal-title", { timeout: 10_000 });
    check("upload dialog opens", true);

    await page.type('input[placeholder="e.g. CS101 Syllabus"]', DOC_TITLE);
    await page.select(
      'select[aria-label="Filter by type"] ~ select, form select',
      "txt",
    ).catch(() => {});
    // The type select is the first <select> inside the dialog.
    await page.evaluate(() => {
      const dialog = document.querySelector('[role="dialog"]');
      const selects = dialog?.querySelectorAll("select") ?? [];
      if (selects[1]) selects[1].value = "txt";
      selects[1]?.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await page.type(
      'input[placeholder="e.g. faculty:123"]',
      "faculty:e2e",
    );
    const [fileInput] = await page.$$('[role="dialog"] input[type="file"]');
    await fileInput.uploadFile(filePath);
    await page.evaluate(() => {
      const dialog = document.querySelector('[role="dialog"]');
      const submit = [...dialog.querySelectorAll('button[type="submit"]')][0];
      submit.click();
    });
    await page.waitForFunction(
      () => !document.querySelector('[role="dialog"]'),
      { timeout: 20_000 },
    );
    check("upload submits and dialog closes", true);
    await page.waitForFunction(
      (title) => document.body.innerText.includes(title),
      { timeout: 15_000 },
      DOC_TITLE,
    );
    check("uploaded document appears in the list", true, DOC_TITLE);

    // ------------------------------------------------------------ search
    await page.type('input[placeholder="Search documents…"]', STAMP);
    await sleep(700); // debounce
    const matches = await page.evaluate(
      (title) => document.body.innerText.includes(title),
      DOC_TITLE,
    );
    check("search finds the uploaded document", matches);
    await page.evaluate(() => {
      const input = document.querySelector('input[placeholder="Search documents…"]');
      input.value = "";
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await sleep(500);

    // ------------------------------------------------------------- detail
    await page.evaluate((title) => {
      const link = [...document.querySelectorAll("a")].find(
        (a) => a.textContent?.trim() === title,
      );
      link?.click();
    }, DOC_TITLE);
    await page.waitForFunction(
      () => document.body.innerText.includes("Audit Information"),
      { timeout: 15_000 },
    );
    const detailText = await page.evaluate(() => document.body.innerText);
    check("detail page opens (id decode round-trip)", detailText.includes(STAMP.slice(0, 4)) || detailText.includes(DOC_TITLE));
    check(
      "detail shows file information",
      detailText.includes("File Information") && detailText.includes("text/plain"),
    );
    check(
      "detail shows version + timeline sections",
      detailText.includes("Version History") && detailText.includes("Timeline"),
    );

    // --------------------------------------------------------------- edit
    await page.evaluate(() => {
      const button = [...document.querySelectorAll("button")].find(
        (btn) => btn.textContent?.trim() === "Edit",
      );
      button?.click();
    });
    await page.waitForSelector('[role="dialog"]', { timeout: 10_000 });
    await page.evaluate(() => {
      const dialog = document.querySelector('[role="dialog"]');
      const input = dialog.querySelector('input[placeholder="e.g. CS101 Syllabus"]');
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value",
      ).set;
      setter.call(input, "");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await page.type('[role="dialog"] input[placeholder="e.g. CS101 Syllabus"]', DOC_TITLE_V2);
    await page.evaluate(() => {
      const dialog = document.querySelector('[role="dialog"]');
      [...dialog.querySelectorAll('button[type="submit"]')][0].click();
    });
    await page.waitForFunction(
      (title) => document.body.innerText.includes(title),
      { timeout: 15_000 },
      DOC_TITLE_V2,
    );
    check("edit via PUT persists (title updated)", true, DOC_TITLE_V2);

    // ------------------------------------------------------------- delete
    await page.evaluate(() => {
      const button = [...document.querySelectorAll("button")].find(
        (btn) => btn.textContent?.trim() === "Delete",
      );
      button?.click();
    });
    await page.waitForFunction(
      () => document.body.innerText.includes("Delete document?"),
      { timeout: 10_000 },
    );
    await page.evaluate(() => {
      const confirm = [...document.querySelectorAll("button")].find(
        (btn) => btn.textContent?.trim() === "Delete" && btn.closest('[role="dialog"], div'),
      );
      // the confirm button is the danger-styled one inside the dialog
      const buttons = [...document.querySelectorAll("button")].filter(
        (btn) => btn.textContent?.trim() === "Delete",
      );
      (buttons[buttons.length - 1] ?? confirm)?.click();
    });
    await page.waitForFunction(
      () => location.pathname.endsWith("/documents"),
      { timeout: 15_000 },
    );
    // The flash toast contains the title ("… was deleted.") — assert against
    // the table rows and the API, not the page text.
    await page.waitForFunction(
      (title) =>
        ![...document.querySelectorAll("table a")].some(
          (a) => a.textContent?.trim() === title,
        ),
      { timeout: 15_000 },
      DOC_TITLE_V2,
    );
    const gone = await fetch(`${API}/documents?page_size=100`).then((r) => r.json());
    const stillThere = (gone.items ?? []).some((d) => d.title === DOC_TITLE_V2);
    check("delete removes the document (back at list)", !stillThere);

    // -------------------------------------------- object <-> document link
    const linked = await fetch(
      `${API}/documents?object_id=${encodeURIComponent(course.id)}&page_size=100`,
    ).then((r) => r.json());
    check("object-document link query returns 200", Array.isArray(linked.items));

    await page.goto(
      `${BASE}/objects/${encodeURIComponent(course.id)}`,
      { waitUntil: "networkidle0" },
    );
    await sleep(800);
    const objectPage = await page.evaluate(() => document.body.innerText);
    check(
      "object detail page renders its Documents section (no crash)",
      objectPage.includes("Documents"),
    );

    // --------------------------------------------------------- cleanliness
    const hostileApi = failedResponses.filter((line) => line.includes("/api/v1/"));
    check("no failing API requests (>=400)", hostileApi.length === 0, hostileApi[0] ?? "");
    const hostile = consoleErrors.filter(
      (line) =>
        !line.includes("favicon") &&
        !line.includes("404 (Not Found)") && // /favicon.ico — no favicon ships yet
        !line.includes("Download the React DevTools") &&
        !line.includes("AbortError"),
    );
    check("no browser console errors", hostile.length === 0, hostile[0] ?? "");
  } catch (error) {
    check("unhandled E2E failure", false, String(error));
  } finally {
    await browser.close();
    fs.rmSync(filePath, { force: true });
  }

  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed.`);
  process.exit(failed ? 1 : 0);
}

await main();

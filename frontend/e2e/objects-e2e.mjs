/**
 * Objects module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   list -> search -> paginate -> open detail (id decode) -> edit -> delete.
 *
 * Usage:
 *   node tests/objects-e2e.mjs            # http://127.0.0.1:3000
 */
import puppeteer from "puppeteer";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

const results = [];
const check = (name, ok, extra = "") => {
  results.push({ name, ok, extra });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? ` — ${extra}` : ""}`);
};

const text = (page, selector) =>
  page.$eval(selector, (el) => el.textContent?.trim() ?? "").catch(() => "");

async function main() {
  const seed = await fetch(`${API}/objects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      object_type: "research_project",
      title: "E2E Quantum Optics Study",
      created_by: "faculty:e2e",
      status: "draft",
      metadata: [
        { key: "department", value: "Physics" },
        { key: "funding", value: "internal" },
      ],
    }),
  }).then((r) => r.json());

  const browser = await puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  const requests = [];
  page.on("request", (req) => {
    if (req.url().includes("/api/v1/")) requests.push(`${req.method()} ${req.url()}`);
  });

  // ---------------------------------------------------------------- list
  await page.goto(`${BASE}/objects`, { waitUntil: "networkidle0" });
  await page.waitForSelector("tbody tr[role='link']", { timeout: 15000 });
  const rowCount = await page.$$eval("tbody tr[role='link']", (rows) => rows.length);
  check("Objects list renders rows", rowCount > 0, `${rowCount} rows`);
  check(
    "List paginates at 12 rows/page",
    rowCount <= 12,
    `${rowCount} rows on page 1`,
  );

  // -------------------------------------------------------------- search
  const before = requests.length;
  await page.type("input[type='search']", "quantum optics", { delay: 20 });
  await new Promise((r) => setTimeout(r, 1200));
  const matches = await page.$$eval("tbody tr[role='link'] a", (as) => as.map((a) => a.textContent));
  check(
    "Debounced search filters (title tokens)",
    matches.length > 0 && matches.every((m) => m.includes("Quantum Optics")),
    JSON.stringify(matches),
  );
  const searchRequests = requests.slice(before).length;
  check("Search issues <= 1 request (debounced)", searchRequests <= 1, `${searchRequests} requests`);

  // search by metadata value
  await page.$eval("input[type='search']", (el) => {
    el.value = "";
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await page.type("input[type='search']", "internal", { delay: 20 });
  await new Promise((r) => setTimeout(r, 900));
  const metaMatches = await page.$$eval("tbody tr[role='link'] a", (as) => as.length);
  check("Search matches metadata values", metaMatches >= 1, `${metaMatches} match(es)`);

  // clear
  await page.click("button[aria-label='Clear search']");
  await new Promise((r) => setTimeout(r, 700));

  // ------------------------------------------------------- detail (decode)
  await page.goto(`${BASE}/objects`, { waitUntil: "networkidle0" });
  await page.waitForSelector("tbody tr[role='link'] a");
  const [link] = await page.$$("tbody tr[role='link'] a");
  const href = await page.evaluate((el) => el.getAttribute("href"), link);
  check("List link encodes the id exactly once", href.includes("%3A") && !href.includes("%253A"), href);

  await Promise.all([page.waitForNavigation({ waitUntil: "networkidle0" }), link.click()]);
  await page.waitForSelector("h1", { timeout: 15000 });
  const detailTitle = await text(page, "h1");
  check("Detail page loads the object (single decode)", detailTitle.length > 0, detailTitle);

  const detailRequest = requests.filter((r) => r.includes("/objects/")).pop() ?? "";
  check(
    "API request carries a decoded id (no %3A / %253A)",
    !detailRequest.includes("%3A"),
    detailRequest,
  );

  const bodyText = await page.evaluate(() => document.body.innerText);
  for (const section of [
    "Overview",
    "Audit Information",
    "Metadata",
    "Version",
    "Relationships",
    "Timeline",
    "Documents",
    "Activity",
  ]) {
    check(`Detail section "${section}" present`, bodyText.includes(section));
  }

  // ------------------------------------------------------------- browser refresh
  await page.reload({ waitUntil: "networkidle0" });
  await page.waitForSelector("h1");
  check("Detail survives a hard browser refresh", (await text(page, "h1")).length > 0);

  // ---------------------------------------------------------------- edit
  await page.goto(`${BASE}/objects/${encodeURIComponent(seed.id)}`, { waitUntil: "networkidle0" });
  await page.waitForSelector("h1");
  const editBtn = await page.$$eval("button", (bs) =>
    bs.findIndex((b) => b.textContent.trim().startsWith("Edit")),
  );
  const buttons = await page.$$("button");
  await buttons[editBtn].click();
  await page.waitForSelector("form[role='dialog']");

  const prefilled = await page.$$eval("form[role='dialog'] input", (inputs) =>
    inputs.map((i) => i.value),
  );
  check(
    "Edit modal prefills fields",
    prefilled.includes("E2E Quantum Optics Study") && prefilled.includes("Physics"),
    JSON.stringify(prefilled.slice(0, 5)),
  );

  const readOnly = await page.$$eval("form[role='dialog'] input", (inputs) =>
    inputs.filter((i) => i.disabled).length,
  );
  check("Immutable fields are disabled in edit mode", readOnly >= 2, `${readOnly} disabled inputs`);

  // change department + add a metadata row
  const deptInput = await page.$$("form[role='dialog'] input");
  await deptInput[2].click({ clickCount: 3 }); // department (title/createdBy/updatedBy before it are disabled)
  await page.evaluate(() => {
    const inputs = [...document.querySelectorAll("form[role='dialog'] input")].filter(
      (i) => !i.disabled,
    );
    const dept = inputs.find((i) => i.placeholder === "e.g. Computer Science");
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    setter.call(dept, "Applied Physics");
    dept.dispatchEvent(new Event("input", { bubbles: true }));
  });

  // duplicate-key guard
  await page.evaluate(() => {
    const addBtn = [...document.querySelectorAll("form[role='dialog'] button")].find((b) =>
      b.textContent.includes("Add row"),
    );
    addBtn.click();
    addBtn.click();
  });
  await page.evaluate(() => {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    const keys = [...document.querySelectorAll("form[role='dialog'] input[aria-label^='Metadata key']")];
    const last = keys.slice(-2);
    for (const input of last) {
      setter.call(input, "duplicate");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });
  await new Promise((r) => setTimeout(r, 200));
  let dialogText = await page.$eval("form[role='dialog']", (el) => el.innerText);
  check("Duplicate metadata key is rejected inline", dialogText.includes("Duplicate key"));

  // reserved department key guard
  await page.evaluate(() => {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    const keys = [...document.querySelectorAll("form[role='dialog'] input[aria-label^='Metadata key']")];
    const last = keys[keys.length - 1];
    setter.call(last, "department");
    last.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await new Promise((r) => setTimeout(r, 200));
  dialogText = await page.$eval("form[role='dialog']", (el) => el.innerText);
  check("Reserved 'department' key is rejected inline", dialogText.includes("reserved"));

  // remove the two offending rows, then save
  await page.evaluate(() => {
    const removes = [...document.querySelectorAll("form[role='dialog'] button[aria-label^='Remove metadata row']")];
    removes.slice(-2).reverse().forEach((b) => b.click());
  });
  await new Promise((r) => setTimeout(r, 200));

  await page.evaluate(() => {
    const submit = [...document.querySelectorAll("form[role='dialog'] button")].find(
      (b) => b.type === "submit",
    );
    submit.click();
  });
  await page.waitForFunction(() => !document.querySelector("form[role='dialog']"), { timeout: 15000 });
  await page.waitForSelector("[role='status']", { timeout: 10000 });
  const toastText = await text(page, "[role='status']");
  check("Update shows a success toast", /updated successfully/i.test(toastText), toastText);

  await new Promise((r) => setTimeout(r, 800));
  const afterEdit = await page.evaluate(() => document.body.innerText);
  check("Detail refreshes with the new value", afterEdit.includes("Applied Physics"));

  const persisted = await fetch(`${API}/objects/${seed.id}`).then((r) => r.json());
  check(
    "PUT persisted to the backend",
    persisted.metadata.department === "Applied Physics",
    JSON.stringify(persisted.metadata),
  );

  // -------------------------------------------------------------- delete
  await page.evaluate(() => {
    const del = [...document.querySelectorAll("button")].find((b) =>
      b.textContent.trim().startsWith("Delete"),
    );
    del.click();
  });
  await page.waitForSelector("[role='alertdialog']");
  const confirmText = await text(page, "[role='alertdialog']");
  check(
    "Confirm dialog shows the object title",
    confirmText.includes("Delete object?") && confirmText.includes("E2E Quantum Optics Study"),
  );

  await Promise.all([
    page.waitForFunction(() => location.pathname === "/objects", { timeout: 15000 }),
    page.evaluate(() => {
      const confirm = [...document.querySelectorAll("[role='alertdialog'] button")].find(
        (b) => b.textContent.trim() === "Delete",
      );
      confirm.click();
    }),
  ]);
  await page.waitForSelector("[role='status']", { timeout: 10000 });
  const deleteToast = await text(page, "[role='status']");
  check("Delete redirects to /objects with a toast", /was deleted/i.test(deleteToast), deleteToast);

  const gone = await fetch(`${API}/objects/${seed.id}`).then((r) => r.status);
  check("Object is gone from the backend", gone === 404, `GET -> ${gone}`);

  // Read the table only — the success toast legitimately repeats the title.
  const listRows = await page
    .$$eval("tbody tr", (rows) => rows.map((r) => r.innerText).join(" "))
    .catch(() => "");
  check("List no longer shows the deleted object", !listRows.includes("E2E Quantum Optics Study"));

  // ------------------------------------------------------------ 404 route
  await page.goto(`${BASE}/objects/${encodeURIComponent("obj:course:NOPE000000000000")}`, {
    waitUntil: "networkidle0",
  });
  await new Promise((r) => setTimeout(r, 800));
  const notFoundText = await page.evaluate(() => document.body.innerText);
  check("Unknown id renders the not-found state", notFoundText.includes("Object not found"));

  // ------------------------------------------------------------- mobile
  await page.setViewport({ width: 375, height: 812 });
  await page.goto(`${BASE}/objects`, { waitUntil: "networkidle0" });
  await page.waitForSelector("tbody tr[role='link']");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  check("No horizontal overflow at 375px", overflow <= 1, `${overflow}px`);

  // Expected 404s: the deliberate unknown-id probe and the missing favicon.
  const unexpected = consoleErrors.filter(
    (e) => !/404|favicon/i.test(e),
  );
  check(
    "No unexpected console/runtime errors during the run",
    unexpected.length === 0,
    unexpected.slice(0, 3).join(" | "),
  );

  await browser.close();

  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  if (failed.length) process.exitCode = 1;
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});

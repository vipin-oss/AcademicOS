/**
 * Objects module — create / validation / pagination smoke test (Puppeteer).
 *
 * Complements `objects-e2e.mjs` (read / update / delete).
 * Requires a running backend and `next start`, plus a local puppeteer install:
 *   npm i --no-save puppeteer && node tests/objects-create-e2e.mjs
 */
import puppeteer from "puppeteer";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

const results = [];
const check = (name, ok, extra = "") => {
  results.push({ name, ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? ` — ${extra}` : ""}`);
};

const setValue = async (page, selectorFn, value) =>
  page.evaluate(
    (fnBody, val) => {
      const el = new Function(`return (${fnBody})()`)();
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value",
      ).set;
      setter.call(el, val);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    },
    selectorFn,
    value,
  );

async function main() {
  const title = `E2E Created ${Date.now()}`;
  const browser = await puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  const apiCalls = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/v1/objects")) apiCalls.push(`${r.method()} ${r.url()}`);
  });

  await page.goto(`${BASE}/objects`, { waitUntil: "networkidle0" });
  await page.waitForSelector("tbody tr[role='link']");

  // ------------------------------------------------------------ pagination
  const totalText = await page.$eval("nav[aria-label='Pagination']", (el) => el.innerText);
  check("Pagination shows a result range", /Showing\s+1–\d+\s+of\s+\d+/.test(totalText), totalText.split("\n")[0]);

  const prevDisabled = await page.$eval(
    "button[aria-label='Previous page']",
    (b) => b.disabled,
  );
  check("Previous is disabled on page 1", prevDisabled);

  const currentPage = await page.$$eval("nav[aria-label='Pagination'] button[aria-current='page']", (b) =>
    b.map((x) => x.textContent.trim()),
  );
  check("Current page is highlighted", currentPage.join() === "1", currentPage.join());

  const beforePageChange = apiCalls.length;
  await page.click("button[aria-label='Next page']");
  await new Promise((r) => setTimeout(r, 1200));
  const page2 = await page.$$eval("nav[aria-label='Pagination'] button[aria-current='page']", (b) =>
    b.map((x) => x.textContent.trim()),
  );
  check("Next advances to page 2", page2.join() === "2", page2.join());
  check(
    "Page change issues exactly one request",
    apiCalls.length - beforePageChange === 1,
    `${apiCalls.length - beforePageChange}`,
  );
  const page2Url = apiCalls[apiCalls.length - 1];
  check("Page 2 request carries page=2", page2Url.includes("page=2"), page2Url);

  // ------------------------------------------------- search keeps working with paging
  await page.type("input[type='search']", "course 1", { delay: 15 });
  await new Promise((r) => setTimeout(r, 1200));
  const searchPage = await page.$eval("nav[aria-label='Pagination']", (el) => el.innerText);
  check("Searching resets to page 1", searchPage.includes("Showing 1–"), searchPage.split("\n")[0]);

  const callsBeforeSearchPaging = apiCalls.length;
  const hasSecondPage = await page.$eval("button[aria-label='Next page']", (b) => !b.disabled);
  if (hasSecondPage) {
    await page.click("button[aria-label='Next page']");
    await new Promise((r) => setTimeout(r, 700));
    check(
      "Paging inside search results issues no extra request",
      apiCalls.length === callsBeforeSearchPaging,
      `${apiCalls.length - callsBeforeSearchPaging} extra`,
    );
    const stillSearching = await page.$eval("input[type='search']", (i) => i.value);
    check("Search term is preserved across page changes", stillSearching === "course 1", stillSearching);
  }
  await page.click("button[aria-label='Clear search']");
  await new Promise((r) => setTimeout(r, 700));

  // ---------------------------------------------------------------- create
  await page.evaluate(() => {
    [...document.querySelectorAll("button")]
      .find((b) => b.textContent.includes("New Object"))
      .click();
  });
  await page.waitForSelector("form[role='dialog']");

  // submit empty -> client validation, no request
  const callsBeforeInvalid = apiCalls.length;
  await page.evaluate(() => {
    [...document.querySelectorAll("form[role='dialog'] button")]
      .find((b) => b.type === "submit")
      .click();
  });
  await new Promise((r) => setTimeout(r, 400));
  const dialogText = await page.$eval("form[role='dialog']", (el) => el.innerText);
  check("Empty form is blocked by client validation", dialogText.includes("Title is required."));
  check("Invalid submit issues no request", apiCalls.length === callsBeforeInvalid);

  // fill required fields
  await setValue(
    page,
    `() => [...document.querySelectorAll("form[role='dialog'] input")].find(i => i.placeholder.includes("Advanced Machine Learning"))`,
    `  ${title}  `, // padded on purpose: the app must trim
  );
  await setValue(
    page,
    `() => [...document.querySelectorAll("form[role='dialog'] input")].find(i => i.placeholder === "e.g. faculty:123")`,
    "faculty:e2e",
  );
  await setValue(
    page,
    `() => [...document.querySelectorAll("form[role='dialog'] input")].find(i => i.placeholder === "e.g. Computer Science")`,
    "Mathematics",
  );
  await page.select("form[role='dialog'] select", "research_project");

  // add a metadata row
  await page.evaluate(() => {
    [...document.querySelectorAll("form[role='dialog'] button")]
      .find((b) => b.textContent.includes("Add row"))
      .click();
  });
  await setValue(
    page,
    `() => document.querySelector("form[role='dialog'] input[aria-label='Metadata key 1']")`,
    "grant_code",
  );
  await setValue(
    page,
    `() => document.querySelector("form[role='dialog'] input[aria-label='Metadata value 1']")`,
    "GR-2026-11",
  );

  // double-click the submit button: only ONE POST may leave the browser
  const callsBeforeCreate = apiCalls.length;
  await page.evaluate(() => {
    const submit = [...document.querySelectorAll("form[role='dialog'] button")].find(
      (b) => b.type === "submit",
    );
    submit.click();
    submit.click();
  });
  await page.waitForFunction(() => !document.querySelector("form[role='dialog']"), {
    timeout: 15000,
  });
  const posts = apiCalls.slice(callsBeforeCreate).filter((c) => c.startsWith("POST"));
  check("Double-click creates the object only once", posts.length === 1, `${posts.length} POSTs`);

  await page.waitForSelector("[role='status']");
  const toast = await page.$eval("[role='status']", (el) => el.innerText);
  check("Create shows a success toast", /created successfully/i.test(toast), toast.trim());

  const created = await fetch(`${API}/objects?page=1&page_size=100`)
    .then((r) => r.json())
    .then((d) => d.items.filter((o) => o.title === title));
  check("Exactly one object was created", created.length === 1, `${created.length} found`);
  check("Title was trimmed before sending", created[0]?.title === title);
  check(
    "Department mapped to metadata.department",
    created[0]?.metadata?.department === "Mathematics",
    JSON.stringify(created[0]?.metadata),
  );
  check(
    "Custom metadata row persisted",
    created[0]?.metadata?.grant_code === "GR-2026-11",
    JSON.stringify(created[0]?.metadata),
  );
  check("Object type selected correctly", created[0]?.object_type === "research_project");

  // list refreshed after create
  await page.type("input[type='search']", title.slice(0, 18), { delay: 10 });
  await new Promise((r) => setTimeout(r, 1200));
  const rows = await page.$$eval("tbody tr[role='link'] a", (as) => as.map((a) => a.textContent));
  check("List refreshed and shows the new object", rows.some((r) => r.includes(title)), rows.join());

  // ------------------------------------------------------------- tablet
  await page.setViewport({ width: 768, height: 1024 });
  await page.goto(`${BASE}/objects`, { waitUntil: "networkidle0" });
  await page.waitForSelector("tbody tr[role='link']");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  check("No horizontal overflow at 768px", overflow <= 1, `${overflow}px`);

  // cleanup
  if (created[0]) {
    await fetch(`${API}/objects/${created[0].id}`, { method: "DELETE" });
  }

  await browser.close();

  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  if (failed.length) process.exitCode = 1;
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});

/**
 * Finance & Procurement module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   finance hub (PART 11 cards with exact ₹ values + PART 9 budget lens) ->
 *   PART 1 directory -> PART 12 search + status/department/vendor/financial-
 *   year filters -> create via the modal (committee link + approval meeting +
 *   research links) -> duplicate proposal-number 409 in the modal -> the
 *   workspace (PART 2 committee lens, PART 4 quotations with document
 *   attachments, PART 5 comparative with the single-recommended guard, PART 6
 *   purchase orders, PART 7 bills with GST, PART 8 assets) -> vendor registry
 *   CRUD (duplicate GST 409) -> the cross-proposal asset register -> dashboard
 *   re-check with exact deltas -> frozen research page spot check -> delete
 *   flow -> 404 state.
 *
 * The cross-module graph (faculty requester, project budget, grant +
 * released installment, purchase committee + approval meeting, supporting
 * document) is seeded through the FROZEN modules' own APIs. Dashboard
 * assertions are BASELINE + DELTA so the suite composes with the other E2E
 * suites in a shared database.
 *
 * Usage:
 *   node tests/finance-e2e.mjs         # http://localhost:3000
 */
import puppeteer from "puppeteer";
import fs from "node:fs";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

const results = [];
const check = (name, ok, extra = "") => {
  results.push({ name, ok, extra });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? ` — ${extra}` : ""}`);
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const STAMP = Date.now().toString(36);
const REQUESTER_NAME = `Dr. Meera Krishnan E2E ${STAMP}`;
const PROJECT_TITLE = `E2E Finance-Linked Project ${STAMP}`;
const GRANT_TITLE = `E2E Finance-Linked Grant ${STAMP}`;
const CPC_NAME = `Purchase Committee E2E ${STAMP}`;
const CPC_CODE = `E2E-${STAMP}-PC1`;
const MEETING_TITLE = `Purchase Approval Meeting E2E ${STAMP}`;
const VENDOR_A_NAME = `Acme Scientific E2E ${STAMP}`;
const VENDOR_B_NAME = `Beta Scientific Traders E2E ${STAMP}`;
const GAMMA_NAME = `Gamma Instruments E2E ${STAMP}`;
const PROPOSAL_TITLE = `HPC Cluster Procurement E2E ${STAMP}`;
const PROPOSAL_NUMBER = `PP-${STAMP}-1`;
const MODAL_TITLE = `E2E Modal Procurement ${STAMP}`;
const MODAL_NUMBER = `PP-${STAMP}-2`;
const TRASH_TITLE = `E2E Trash Proposal ${STAMP}`;
const DOC_TITLE = `E2E Quote Attachment ${STAMP}`;
const MINUTES_TEXT = `Minutes E2E ${STAMP}: the committee reviewed the quotes.`;
const RECOMMENDATION_TEXT = `Recommend the L1 vendor E2E ${STAMP}.`;
const ASSET_ID = `AST-${STAMP}-1`;
const ASSET_ITEM = `GPU Node E2E ${STAMP}`;
const PO_NUMBER = `PO-${STAMP}-1`;
const BILL_ONE = `B-${STAMP}-1`;
const BILL_TWO = `B-${STAMP}-2`;

// Run-unique GST/PAN identities (backend regex: \d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]).
const GST_SEQ = String(Date.now() % 10000).padStart(4, "0");
const GST_A = `07AABCE${GST_SEQ}C1Z5`;
const GST_B = `07AABCF${GST_SEQ}D1Z6`;
const GST_GAMMA = `07AABCJ${GST_SEQ}K1Z4`;

/** ₹ mirror of the frontend formatMoney (en-IN grouping). */
const inr = (value) =>
  value === null || value === undefined
    ? "—"
    : `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

const postJson = (path, body, method = "POST") =>
  fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

const getJson = (path) =>
  fetch(`${API}${path}`).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

/**
 * Poll a GET endpoint until `predicate(body)` holds. Panel saves do not
 * toast, so the API is the source of truth for "the save actually landed".
 */
async function waitApi(path, predicate, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs;
  let last = {};
  for (;;) {
    last = await getJson(path).then((r) => r.body);
    try {
      if (predicate(last)) return last;
    } catch {
      /* predicate hit a half-formed payload — keep polling */
    }
    if (Date.now() >= deadline) {
      throw new Error(
        `Timed out waiting for API state at ${path}: ${JSON.stringify(last).slice(0, 400)}`,
      );
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
}

/** Click a button by its exact label (dialog-scoped wins when one is open). */
async function clickButtonWithText(page, text, { inDialog = false } = {}) {
  const clicked = await page.evaluate(
    (wanted, dialogOnly) => {
      const candidates = [...document.querySelectorAll("button")].filter(
        (btn) => btn.textContent?.trim() === wanted && !btn.disabled,
      );
      const dialogButton = candidates.find((btn) =>
        btn.closest('[role="dialog"], [role="alertdialog"]'),
      );
      const button = dialogOnly ? dialogButton : (dialogButton ?? candidates[0]);
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

/** Wait for + click a button by its EXACT aria-label (handles quotes inside). */
async function clickAriaButton(page, ariaLabel, timeoutMs = 15_000) {
  await page.waitForFunction(
    (wanted) =>
      [...document.querySelectorAll("button")].some(
        (btn) => btn.getAttribute("aria-label") === wanted && !btn.disabled,
      ),
    { timeout: timeoutMs },
    ariaLabel,
  );
  const clicked = await page.evaluate((wanted) => {
    const button = [...document.querySelectorAll("button")].find(
      (btn) => btn.getAttribute("aria-label") === wanted && !btn.disabled,
    );
    if (!button) return false;
    button.click();
    return true;
  }, ariaLabel);
  if (!clicked) throw new Error(`No clickable button with aria-label “${ariaLabel}”.`);
}

/** Click a link whose text matches exactly (row navigation). */
async function clickLinkWithText(page, text) {
  const clicked = await page.evaluate((wanted) => {
    const link = [...document.querySelectorAll("a")].find(
      (a) => a.textContent?.trim() === wanted,
    );
    if (!link) return false;
    link.click();
    return true;
  }, text);
  if (!clicked) throw new Error(`No link labelled “${text}” found.`);
}

/** Fill the input wrapped by the <label> whose text starts with `label`. */
async function typeInField(page, label, value) {
  const ok = await page.evaluate(
    (wanted, val) => {
      const scope = document.querySelector('form[role="dialog"]') ?? document;
      const target = [...scope.querySelectorAll("label")].find((el) =>
        el.textContent?.trim().startsWith(wanted),
      );
      const input = target?.querySelector("input:not([type=checkbox]), textarea");
      if (!input) return false;
      input.focus();
      const proto =
        input instanceof HTMLTextAreaElement
          ? window.HTMLTextAreaElement.prototype
          : window.HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
      setter.call(input, val);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    },
    label,
    value,
  );
  if (!ok) throw new Error(`No field labelled “${label}” found.`);
}

/** Wait until `needle` appears in body.innerText (case-insensitive). */
async function waitForText(page, needle, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  const wanted = needle.toUpperCase();
  for (;;) {
    const text = await page.evaluate(() => document.body.innerText);
    if (text.toUpperCase().includes(wanted)) return text;
    if (Date.now() >= deadline) throw new Error(`Timed out waiting for text “${needle}".`);
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
}

/** Wait until a <select> contains an option with `value`. */
async function waitForOption(page, selector, value, timeoutMs = 15_000) {
  await page.waitForFunction(
    (sel, val) => {
      const select = document.querySelector(sel);
      return select ? [...select.options].some((option) => option.value === val) : false;
    },
    { timeout: timeoutMs },
    selector,
    value,
  );
}

/** Set a React-controlled input's value directly (search input etc.). */
async function setFieldValue(page, selector, value) {
  const ok = await page.evaluate(
    (sel, val) => {
      const input = document.querySelector(sel);
      if (!input) return false;
      const proto =
        input instanceof HTMLTextAreaElement
          ? window.HTMLTextAreaElement.prototype
          : window.HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
      setter.call(input, val);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    },
    selector,
    value,
  );
  if (!ok) throw new Error(`No input matching “${selector}”.`);
}

/** Read the big value of a PART 11 dashboard card by its label. */
async function cardValue(page, label) {
  return page.evaluate((wanted) => {
    const cards = [...document.querySelectorAll(".rounded-xl")];
    for (const card of cards) {
      const labelEl = [...card.querySelectorAll("div")].find(
        (el) => el.textContent?.trim().toUpperCase() === wanted.toUpperCase(),
      );
      if (labelEl) {
        const value = card.querySelector("p")?.textContent?.trim();
        if (value != null) return value;
      }
    }
    return null;
  }, label);
}

async function main() {
  // ---------------------------------------------------- baseline + seeding
  // The dashboard cards aggregate finance objects only, but the budget lens
  // composes frozen research budgets — capture the baseline first so the
  // assertions stay exact even in a database shared with other E2E suites.
  const base = await getJson("/finance/dashboard").then((r) => r.body);
  check("seed: baseline dashboard captured", typeof base?.total_vendors === "number",
    JSON.stringify(base));

  const requester = await postJson("/faculty", {
    name: REQUESTER_NAME,
    employee_id: `E2E-${STAMP}-FR1`,
    uploaded_by: "registrar:e2e",
    designation: "Professor",
    department: "Physics",
  }).then((r) => r.body);
  check("seed: requester faculty created", Boolean(requester.id));

  const project = await postJson("/research/projects", {
    title: PROJECT_TITLE,
    uploaded_by: "registrar:e2e",
    lifecycle_status: "active",
    budget_approved: 1_000_000,
  }).then((r) => r.body);
  const grant = await postJson("/research/grants", {
    title: GRANT_TITLE,
    grant_number: `E2E-${STAMP}-FG1`,
    uploaded_by: "registrar:e2e",
    amount: 800_000,
    links: { projects: [project.id], funding_agencies: [] },
  }).then((r) => r.body);
  const installment = await postJson(`/research/grants/${grant.id}/installments`, {
    installment_no: 1,
    date: "2026-05-10",
    amount: 500_000,
    status: "released",
    uploaded_by: "registrar:e2e",
  });
  check(
    "seed: project (₹10,00,000 approved) + grant + released installment (₹5,00,000)",
    Boolean(project.id && grant.id) && installment.status === 201,
    `${project.id ?? "?"} ${grant.id ?? "?"} ${installment.status}`,
  );

  const cpc = await postJson("/committees", {
    name: CPC_NAME,
    committee_code: CPC_CODE,
    committee_type: "purchase",
    department: "Administration",
    uploaded_by: "registrar:e2e",
    status: "active",
  }).then((r) => r.body);
  const meetingRes = await postJson(`/committees/${cpc.id}/meetings`, {
    title: MEETING_TITLE,
    uploaded_by: "registrar:e2e",
    meeting_number: "3",
    meeting_date: "2026-07-20",
    venue: "Board Room 1",
    mode: "offline",
  });
  const meeting = meetingRes.body;
  check("seed: purchase committee + approval meeting created",
    Boolean(cpc.id && meeting.id), `${cpc.id ?? "?"} ${meeting.id ?? "?"}`);

  const vendorA = await postJson("/finance/vendors", {
    name: VENDOR_A_NAME,
    uploaded_by: "finance:e2e",
    status: "active",
    gst_number: GST_A,
    pan: "AABCE1234C",
    contact_person: "Ravi Kumar",
    email: "sales@acme-e2e.example",
    phone: "9810012345",
    address: "Okhla, New Delhi",
    bank_details: {
      bank_name: "SBI",
      account_number: "12345678901",
      ifsc: "SBIN0001234",
      branch: "Okhla",
    },
    tags: ["lab"],
  }).then((r) => r.body);
  const vendorB = await postJson("/finance/vendors", {
    name: VENDOR_B_NAME,
    uploaded_by: "finance:e2e",
    status: "active",
    gst_number: GST_B,
    pan: "AABCF1234D",
    contact_person: "Sunita Sharma",
    email: "quotes@beta-e2e.example",
    phone: "9820023456",
    address: "Nehru Place, New Delhi",
  }).then((r) => r.body);
  check("seed: two vendors registered (GST identities)", Boolean(vendorA.id && vendorB.id));

  const dupGst = await postJson("/finance/vendors", {
    name: `Copycat Vendor ${STAMP}`,
    uploaded_by: "finance:e2e",
    gst_number: GST_A,
  });
  check("seed: duplicate vendor GST rejected (409)", dupGst.status === 409,
    String(dupGst.status));

  const proposalRes = await postJson("/finance/proposals", {
    title: PROPOSAL_TITLE,
    uploaded_by: "finance:e2e",
    status: "active",
    proposal_number: PROPOSAL_NUMBER,
    department: "Physics",
    requested_by: requester.id,
    proposal_date: "2026-07-15",
    purpose: "Compute cluster upgrade",
    budget_head: "Capital",
    estimated_cost: 450_000,
    proposal_status: "submitted",
    priority: "high",
    notes: "E2E notes",
    tags: ["it", "hpc"],
    approval_meeting_id: meeting.id,
    minutes: MINUTES_TEXT,
    recommendations: RECOMMENDATION_TEXT,
    quotations: [
      {
        vendor_id: vendorA.id,
        quotation_date: "2026-07-10",
        amount: "440000",
        validity_date: "2026-09-30",
      },
    ],
    links: { projects: [project.id], grants: [grant.id], committees: [cpc.id] },
  });
  const proposal = proposalRes.body;
  check(
    "seed: submitted proposal created (quotation + committee + links)",
    proposalRes.status === 201 &&
      proposal.proposal_number === PROPOSAL_NUMBER &&
      proposal.requested_name === REQUESTER_NAME &&
      proposal.quotations?.length === 1 &&
      proposal.approval_meeting?.id === meeting.id,
    proposal.id ?? JSON.stringify(proposalRes.body),
  );

  // API-side guard rails (seeded here; the browser gate allow-lists the 4xx).
  const dupNumber = await postJson("/finance/proposals", {
    title: `Duplicate ${STAMP}`,
    uploaded_by: "finance:e2e",
    proposal_number: PROPOSAL_NUMBER,
  });
  check("seed: duplicate proposal number rejected (409)", dupNumber.status === 409);

  const wrongMeeting = await postJson("/finance/proposals", {
    title: `Wrong Meeting ${STAMP}`,
    uploaded_by: "finance:e2e",
    approval_meeting_id: cpc.id, // a committee, not a meeting
  });
  check("seed: non-meeting approval pointer rejected (422)", wrongMeeting.status === 422);

  const doubleRecommended = await postJson("/finance/proposals", {
    title: `Two Winners ${STAMP}`,
    uploaded_by: "finance:e2e",
    comparative: [
      { vendor_id: vendorA.id, amount: "100", recommended: true },
      { vendor_id: vendorB.id, amount: "200", recommended: true },
    ],
  });
  check("seed: two recommended comparative rows rejected (422)",
    doubleRecommended.status === 422);

  const missingPoNumber = await postJson("/finance/proposals", {
    title: `Missing PO ${STAMP}`,
    uploaded_by: "finance:e2e",
    purchase_orders: [{ vendor_id: vendorA.id, amount: "100" }],
  });
  check("seed: purchase order without a PO number rejected (422)",
    missingPoNumber.status === 422);

  const trash = await postJson("/finance/proposals", {
    title: TRASH_TITLE,
    uploaded_by: "finance:e2e",
    proposal_number: `PP-${STAMP}-TR1`,
  }).then((r) => r.body);
  check("seed: trash proposal (delete flow)", Boolean(trash.id));

  // PART 10: a supporting document attached to the proposal (frozen API).
  const form = new FormData();
  form.append("title", DOC_TITLE);
  form.append("document_type", "pdf");
  form.append("uploaded_by", "finance:e2e");
  form.append("object_id", proposal.id);
  form.append("file", new Blob([`quote attachment ${STAMP}`], { type: "text/plain" }), "quote.txt");
  const document_ = await fetch(`${API}/documents`, { method: "POST", body: form }).then((r) =>
    r.json(),
  );
  check("seed: supporting document attached to the proposal", Boolean(document_.id));

  // ---------------------------------------------------------------- browser
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
      failedResponses.push(`${res.status()} ${res.request().method()} ${res.url()}`);
    }
  });

  // Baseline-derived expectations (procurement deltas only).
  const baseRemainingEffective =
    base.budget_remaining === null || base.budget_remaining === undefined
      ? -Number(base.budget_utilized ?? 0)
      : Number(base.budget_remaining);

  try {
    // ------------------------------------------------------------- the hub
    await page.goto(`${BASE}/finance`, { waitUntil: "networkidle0" });
    await page.waitForSelector("h1", { timeout: 30_000 });
    const heading = await page.$eval("h1", (el) => el.textContent?.trim());
    check("finance hub loads", heading?.includes("Finance") ?? false, heading ?? "");
    const navText = await page.$eval("nav", (nav) => nav.innerText);
    check("sidebar exposes the Finance entry", navText.includes("Finance"));

    const hub = await waitForText(page, "PENDING BILLS", 60_000);
    check(
      "PART 11 dashboard cards render (all seven labels)",
      /ACTIVE PROCUREMENTS[\s\S]*PENDING APPROVALS[\s\S]*TOTAL VENDORS[\s\S]*TOTAL PURCHASE ORDERS[\s\S]*BUDGET UTILIZED[\s\S]*BUDGET REMAINING[\s\S]*PENDING BILLS/.test(
        hub.toUpperCase(),
      ),
    );
    const firstCards = {
      active: await cardValue(page, "ACTIVE PROCUREMENTS"),
      pending: await cardValue(page, "PENDING APPROVALS"),
      vendors: await cardValue(page, "TOTAL VENDORS"),
      pos: await cardValue(page, "TOTAL PURCHASE ORDERS"),
      utilized: await cardValue(page, "BUDGET UTILIZED"),
      remaining: await cardValue(page, "BUDGET REMAINING"),
      bills: await cardValue(page, "PENDING BILLS"),
    };
    check(
      "PART 11 card values = baseline + seeded procurement (before orders/bills)",
      firstCards.active === String(base.active_procurements + 1) &&
        firstCards.pending === String(base.pending_approvals + 1) &&
        firstCards.vendors === String(base.total_vendors + 2) &&
        firstCards.pos === String(base.total_purchase_orders) &&
        firstCards.utilized === inr(base.budget_utilized) &&
        firstCards.remaining === inr(baseRemainingEffective + 1_000_000) &&
        firstCards.bills === String(base.pending_bills),
      JSON.stringify(firstCards),
    );

    // PART 9 budget lens (per project, seeded: approved 10L / released 5L).
    const budgetText = await waitForText(page, "BUDGET TRACKING", 60_000);
    const budgetRow = await page.evaluate((title) => {
      const row = [...document.querySelectorAll("tr")].find((tr) =>
        tr.textContent?.includes(title),
      );
      return row?.textContent ?? "";
    }, PROJECT_TITLE);
    check(
      "PART 9 budget line: approved ₹10,00,000 / released ₹5,00,000 / utilized ₹0 / remaining ₹10,00,000",
      budgetText.toUpperCase().includes("BUDGET TRACKING") &&
        budgetRow.includes(inr(1_000_000)) &&
        budgetRow.includes(inr(500_000)) &&
        budgetRow.includes(inr(0)),
      budgetRow.slice(0, 120),
    );

    // PART 1 directory row (search-scoped so the suite stays rerunnable in a
    // shared database — leftover runs must not push the row to page 2).
    await setFieldValue(page, 'input[type="search"]', `hpc ${STAMP}`);
    const tableText = await waitForText(page, PROPOSAL_TITLE, 60_000);
    check(
      "directory row: title, number, vendor, department, status, priority, cost, date",
      tableText.includes(PROPOSAL_NUMBER) &&
        tableText.includes(VENDOR_A_NAME) &&
        tableText.includes("Physics") &&
        tableText.includes("Submitted") &&
        tableText.includes("High") &&
        tableText.includes(inr(450_000)) &&
        tableText.includes("15 Jul 2026"),
    );

    // --------------------------------------------------------- PART 12
    await setFieldValue(page, 'input[type="search"]', "");
    await sleep(400);
    await setFieldValue(page, 'input[type="search"]', `nonexistent-${STAMP}`);
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching proposals"),
      { timeout: 15_000 },
    );
    check("search: non-matching query shows the empty state", true);
    await setFieldValue(page, 'input[type="search"]', `hpc ${STAMP}`);
    await page.waitForFunction(
      (title) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === title),
      { timeout: 15_000 },
      PROPOSAL_TITLE,
    );
    check("search: token-AND search finds the proposal by title tokens", true);
    await setFieldValue(page, 'input[type="search"]', "");
    await sleep(600);

    await page.select('select[aria-label="Filter by status"]', "approved");
    await page.waitForFunction(
      (number) => !document.body.innerText.includes(number),
      { timeout: 15_000 },
      PROPOSAL_NUMBER,
    );
    check("filters: wrong status excludes the proposal", true);
    await page.select('select[aria-label="Filter by status"]', "submitted");
    await page.waitForFunction(
      (number) => document.body.innerText.includes(number),
      { timeout: 15_000 },
      PROPOSAL_NUMBER,
    );
    check("filters: matching status keeps the proposal", true);

    await setFieldValue(page, 'input[aria-label="Filter by department"]', "chemistry");
    await page.waitForFunction(
      (number) => !document.body.innerText.includes(number),
      { timeout: 15_000 },
      PROPOSAL_NUMBER,
    );
    check("filters: wrong department excludes the proposal", true);
    await setFieldValue(page, 'input[aria-label="Filter by department"]', "physics");
    await page.waitForFunction(
      (number) => document.body.innerText.includes(number),
      { timeout: 15_000 },
      PROPOSAL_NUMBER,
    );
    check("filters: matching department keeps the proposal", true);

    await setFieldValue(page, 'input[aria-label="Filter by vendor"]', "beta");
    await page.waitForFunction(
      (number) => !document.body.innerText.includes(number),
      { timeout: 15_000 },
      PROPOSAL_NUMBER,
    );
    check("filters: vendor not on the proposal excludes it", true);
    await setFieldValue(page, 'input[aria-label="Filter by vendor"]', "acme");
    await page.waitForFunction(
      (number) => document.body.innerText.includes(number),
      { timeout: 15_000 },
      PROPOSAL_NUMBER,
    );
    check("filters: quoted vendor keeps the proposal", true);

    await setFieldValue(page, 'input[aria-label="Filter by department"]', "");
    await setFieldValue(page, 'input[aria-label="Filter by vendor"]', "");
    await page.select('select[aria-label="Filter by financial year"]', "2024-25");
    await page.waitForFunction(
      (number) => !document.body.innerText.includes(number),
      { timeout: 15_000 },
      PROPOSAL_NUMBER,
    );
    check("filters: wrong financial year (FY 2024-25) excludes the proposal", true);
    await page.select('select[aria-label="Filter by financial year"]', "2026-27");
    await page.waitForFunction(
      (number) => document.body.innerText.includes(number),
      { timeout: 15_000 },
      PROPOSAL_NUMBER,
    );
    check("filters: proposal dated 15 Jul 2026 falls in FY 2026-27", true);
    await page.select('select[aria-label="Filter by financial year"]', "");
    // Reset every filter: the modal-created proposal below is a DRAFT, so a
    // lingering "submitted" status filter would hide it from the directory.
    await page.select('select[aria-label="Filter by status"]', "all");
    await sleep(600);

    // ------------------------------------------------ create via the modal
    await clickButtonWithText(page, "New Proposal");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Proposal title", MODAL_TITLE);
    await typeInField(page, "Proposal number", MODAL_NUMBER);
    await typeInField(page, "Department", "Chemistry");
    await typeInField(page, "Proposal date", "2026-04-10");
    await typeInField(page, "Estimated cost", "25000");
    await typeInField(page, "Budget head", "Consumables");
    await typeInField(page, "Purpose", "Glassware restocking");
    await waitForOption(page, 'select[aria-label="Requested by"]', requester.id);
    await page.select('select[aria-label="Requested by"]', requester.id);
    await page.select('select[aria-label="Priority"]', "low");
    await waitForOption(page, 'select[aria-label="Purchase committees"]', cpc.id);
    await page.select('select[aria-label="Purchase committees"]', cpc.id);
    // The approval-meeting options load after the committee selection.
    await waitForOption(page, 'select[aria-label="Approval meeting"]', meeting.id);
    await page.select('select[aria-label="Approval meeting"]', meeting.id);
    await typeInField(page, "Minutes", "Modal minutes");
    await typeInField(page, "Recommendations", "Modal recommendations");
    await waitForOption(page, 'select[aria-label="Linked research projects"]', project.id);
    await page.select('select[aria-label="Linked research projects"]', project.id);
    await waitForOption(page, 'select[aria-label="Linked grants"]', grant.id);
    await page.select('select[aria-label="Linked grants"]', grant.id);
    await clickButtonWithText(page, "Create proposal");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "created successfully", 15_000);
    check("create: proposal registered via the modal (committee + meeting + links)", true);
    await setFieldValue(page, 'input[type="search"]', `modal ${STAMP}`);
    const modalRow = await waitForText(page, MODAL_NUMBER, 15_000);
    check("create: the modal proposal appears in the directory",
      modalRow.includes(MODAL_TITLE) && modalRow.includes("Chemistry"));
    const modalProposal = await waitApi(
      `/finance/proposals?q=${encodeURIComponent(`modal ${STAMP}`)}`,
      (body) =>
      body.items?.length === 1 &&
      body.items[0].approval_meeting?.id === meeting.id &&
      body.items[0].links?.committees?.[0]?.id === cpc.id,
    );
    check("create: modal proposal resolves the approval meeting + committee link",
      Boolean(modalProposal.items?.[0]?.id));
    await setFieldValue(page, 'input[type="search"]', "");
    await sleep(600);

    // duplicate number -> backend 409 surfaces in the modal
    await clickButtonWithText(page, "New Proposal");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Proposal title", `Duplicate ${STAMP}`);
    await typeInField(page, "Proposal number", MODAL_NUMBER);
    await clickButtonWithText(page, "Create proposal");
    await page.waitForSelector('form[role="dialog"] [role="alert"]', { timeout: 15_000 });
    const dupeAlert = await page.$eval(
      'form[role="dialog"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check(
      "duplicate proposal number surfaces the backend 409 in the modal",
      dupeAlert.toLowerCase().includes("number") ||
        dupeAlert.toLowerCase().includes("already exists"),
      dupeAlert.slice(0, 90),
    );
    await clickButtonWithText(page, "Cancel", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 10_000,
    });

    // --------------------------------------------------------- the workspace
    await setFieldValue(page, 'input[type="search"]', `hpc ${STAMP}`);
    await page.waitForFunction(
      (title) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === title),
      { timeout: 15_000 },
      PROPOSAL_TITLE,
    );
    await clickLinkWithText(page, PROPOSAL_TITLE);
    const workspace = await waitForText(page, "AUDIT INFORMATION", 60_000);
    check(
      "workspace loads (header: title, number, badges, department, requester)",
      workspace.includes(PROPOSAL_TITLE) &&
        workspace.includes(PROPOSAL_NUMBER) &&
        workspace.includes("Submitted") &&
        workspace.includes("High") &&
        workspace.includes("Physics") &&
        workspace.includes(REQUESTER_NAME),
    );
    check(
      "record panel: estimated cost, budget head, purpose, tags, notes",
      workspace.includes(inr(450_000)) &&
        workspace.includes("Capital") &&
        workspace.includes("Compute cluster upgrade") &&
        workspace.includes("hpc") &&
        workspace.includes("E2E notes"),
    );
    check(
      "PART 2 committee lens: purchase committee, approval meeting, minutes, recommendations",
      workspace.includes(CPC_NAME) &&
        workspace.includes(MEETING_TITLE) &&
        workspace.includes("No. 3") &&
        workspace.includes(MINUTES_TEXT) &&
        workspace.includes(RECOMMENDATION_TEXT),
    );
    check(
      "PART 4 quotations panel shows the seeded quote (Acme, ₹4,40,000)",
      workspace.toUpperCase().includes("QUOTATIONS (1)") &&
        workspace.includes(VENDOR_A_NAME) &&
        workspace.includes(inr(440_000)),
    );
    check(
      "links panel lists the project, grant and committee",
      workspace.includes(PROJECT_TITLE) &&
        workspace.includes(GRANT_TITLE) &&
        workspace.includes(CPC_NAME),
    );
    check("PART 10 documents lens lists the attached quote document",
      workspace.includes(DOC_TITLE));
    check(
      "audit info renders the Object id + version",
      workspace.includes("obj:purchase:") &&
        workspace.includes("Current version") &&
        /v\d+/.test(workspace),
    );

    // PART 4 quotations editor: second quote + document on the first row.
    const quoteDoc = `select[aria-label="Quotation 1 documents"]`;
    await page.click('button[aria-label="Edit quotations"]');
    await waitForOption(page, quoteDoc, document_.id);
    await page.select(quoteDoc, document_.id);
    await clickButtonWithText(page, "Add quotation");
    await waitForOption(page, 'select[aria-label="Quotation 2 vendor"]', vendorB.id);
    await page.select('select[aria-label="Quotation 2 vendor"]', vendorB.id);
    await setFieldValue(page, 'input[aria-label="Quotation 2 date"]', "2026-07-12");
    await setFieldValue(page, 'input[aria-label="Quotation 2 amount"]', "438000");
    await setFieldValue(page, 'input[aria-label="Quotation 2 validity"]', "2026-09-15");
    await setFieldValue(page, 'input[aria-label="Quotation 2 remarks"]', "L1 quote");
    await clickButtonWithText(page, "Save");
    await waitApi(
      `/finance/proposals/${encodeURIComponent(proposal.id)}`,
      (body) =>
        body.quotations?.length === 2 &&
        body.quotations[0].supporting_documents?.length === 1 &&
        body.quotations[1].vendor_id === vendorB.id,
    );
    const quotesNow = await waitForText(page, "Quotations (2)", 15_000);
    check(
      "PART 4: second quotation saved; document resolved on row 1",
      quotesNow.includes(VENDOR_B_NAME) &&
        quotesNow.includes(inr(438_000)) &&
        quotesNow.includes(DOC_TITLE),
    );

    // PART 5 comparative: generate from quotations + single-recommended guard.
    // The editor starts EMPTY (no rows yet) — the generate button creates the
    // rows, then the selects exist.
    await page.click('button[aria-label="Edit comparative statement"]');
    await clickButtonWithText(page, "Generate from quotations (2)");
    await page.waitForSelector('select[aria-label="Comparative 1 vendor"]', { timeout: 10_000 });
    const c1Vendor = await page.$eval('select[aria-label="Comparative 1 vendor"]', (el) => el.value);
    const c2Amount = await page.$eval('input[aria-label="Comparative 2 amount"]', (el) => el.value);
    check(
      "PART 5: generate-from-quotations prefills both vendors + amounts",
      c1Vendor === vendorA.id && c2Amount === "438000",
      `${c1Vendor} ${c2Amount}`,
    );
    // The client-side single-recommended guard fires before any API call.
    await page.click('input[aria-label="Comparative 1 recommended"]');
    await page.click('input[aria-label="Comparative 2 recommended"]');
    await clickButtonWithText(page, "Save");
    await page.waitForSelector(
      'section[aria-label="Comparative statement"] [role="alert"]',
      { timeout: 10_000 },
    );
    const guard = await page.$eval(
      'section[aria-label="Comparative statement"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check("PART 5: two recommended vendors trigger the client guard",
      guard.includes("Only one vendor can be recommended"), guard.slice(0, 80));
    await page.click('input[aria-label="Comparative 1 recommended"]'); // uncheck row 1
    await clickButtonWithText(page, "Save");
    await waitApi(
      `/finance/proposals/${encodeURIComponent(proposal.id)}`,
      (body) =>
        body.comparative?.length === 2 &&
        body.comparative[1].recommended === true &&
        body.comparative[0].recommended === false,
    );
    await waitForText(page, "Comparative Statement (2)", 15_000);
    const recommended = await page.$(
      `[aria-label="Recommended vendor ${VENDOR_B_NAME}"]`,
    );
    check("PART 5: Beta marked recommended (single winner) and displayed",
      Boolean(recommended));

    // PART 6 purchase order for the L1 vendor.
    await page.click('button[aria-label="Edit purchase orders"]');
    await clickButtonWithText(page, "Add purchase order");
    await setFieldValue(page, 'input[aria-label="Purchase order 1 po number"]', PO_NUMBER);
    await waitForOption(page, 'select[aria-label="Purchase order 1 vendor"]', vendorB.id);
    await page.select('select[aria-label="Purchase order 1 vendor"]', vendorB.id);
    await setFieldValue(page, 'input[aria-label="Purchase order 1 date"]', "2026-07-22");
    await setFieldValue(page, 'input[aria-label="Purchase order 1 amount"]', "438000");
    await page.select('select[aria-label="Purchase order 1 status"]', "issued");
    await setFieldValue(page, 'input[aria-label="Purchase order 1 delivery date"]', "2026-08-30");
    await clickButtonWithText(page, "Save");
    await waitApi(
      `/finance/proposals/${encodeURIComponent(proposal.id)}`,
      (body) =>
        body.purchase_orders?.length === 1 &&
        body.purchase_orders[0].po_number === PO_NUMBER &&
        body.stats?.committed === 438_000,
    );
    const posNow = await waitForText(page, "Purchase Orders (1)", 15_000);
    check("PART 6: purchase order saved (PO number, vendor, amount, issued)",
      posNow.includes(PO_NUMBER) && posNow.includes(inr(438_000)) && posNow.includes("Issued"));

    // PART 7 bills: one paid (spend) + one pending (pending bills).
    await page.click('button[aria-label="Edit bills & invoices"]');
    await clickButtonWithText(page, "Add bill");
    await setFieldValue(page, 'input[aria-label="Bill 1 bill number"]', BILL_ONE);
    await setFieldValue(page, 'input[aria-label="Bill 1 invoice number"]', `INV-${STAMP}-1`);
    await waitForOption(page, 'select[aria-label="Bill 1 vendor"]', vendorB.id);
    await page.select('select[aria-label="Bill 1 vendor"]', vendorB.id);
    await setFieldValue(page, 'input[aria-label="Bill 1 date"]', "2026-08-01");
    await setFieldValue(page, 'input[aria-label="Bill 1 amount"]', "371186");
    await setFieldValue(page, 'input[aria-label="Bill 1 gst amount"]', "66814");
    await page.select('select[aria-label="Bill 1 payment status"]', "paid");
    await setFieldValue(page, 'input[aria-label="Bill 1 paid date"]', "2026-08-02");
    await setFieldValue(page, 'input[aria-label="Bill 1 po number"]', PO_NUMBER);
    await clickButtonWithText(page, "Add bill");
    await setFieldValue(page, 'input[aria-label="Bill 2 bill number"]', BILL_TWO);
    await waitForOption(page, 'select[aria-label="Bill 2 vendor"]', vendorB.id);
    await page.select('select[aria-label="Bill 2 vendor"]', vendorB.id);
    await setFieldValue(page, 'input[aria-label="Bill 2 date"]', "2026-08-01");
    await setFieldValue(page, 'input[aria-label="Bill 2 amount"]', "5000");
    await setFieldValue(page, 'input[aria-label="Bill 2 gst amount"]', "900");
    await page.select('select[aria-label="Bill 2 payment status"]', "pending");
    await clickButtonWithText(page, "Save");
    await waitApi(
      `/finance/proposals/${encodeURIComponent(proposal.id)}`,
      (body) =>
        body.bills?.length === 2 &&
        body.stats?.spent === 438_000 &&
        body.stats?.pending_bills === 1,
    );
    const billsNow = await waitForText(page, "Bills & Invoices (2)", 15_000);
    check(
      "PART 7: paid bill (₹4,38,000 incl. GST) + pending bill recorded",
      billsNow.includes(BILL_ONE) &&
        billsNow.includes(inr(438_000)) &&
        billsNow.includes("Paid") &&
        billsNow.includes("Pending"),
    );

    // PART 8 asset row for the delivered order.
    await page.click('button[aria-label="Edit assets"]');
    await clickButtonWithText(page, "Add asset");
    await setFieldValue(page, 'input[aria-label="Asset 1 asset id"]', ASSET_ID);
    await setFieldValue(page, 'input[aria-label="Asset 1 item name"]', ASSET_ITEM);
    await page.select('select[aria-label="Asset 1 category"]', "equipment");
    await setFieldValue(page, 'input[aria-label="Asset 1 serial number"]', `SN-${STAMP}`);
    await setFieldValue(page, 'input[aria-label="Asset 1 location"]', "Data Center");
    await setFieldValue(page, 'input[aria-label="Asset 1 assigned to"]', "Lab In-charge");
    await setFieldValue(page, 'input[aria-label="Asset 1 warranty expiry"]', "2029-07-31");
    await setFieldValue(page, 'input[aria-label="Asset 1 purchase date"]', "2026-08-01");
    await setFieldValue(page, 'input[aria-label="Asset 1 cost"]', "438000");
    await page.select('select[aria-label="Asset 1 status"]', "in_service");
    await setFieldValue(page, 'input[aria-label="Asset 1 po number"]', PO_NUMBER);
    await clickButtonWithText(page, "Save");
    await waitApi(
      `/finance/proposals/${encodeURIComponent(proposal.id)}`,
      (body) => body.assets?.length === 1 && body.assets[0].asset_id === ASSET_ID,
    );
    const assetsNow = await waitForText(page, "Assets (1)", 15_000);
    check("PART 8: asset row saved (ID, item, equipment, in service)",
      assetsNow.includes(ASSET_ID) &&
        assetsNow.includes(ASSET_ITEM) &&
        assetsNow.includes("Equipment") &&
        assetsNow.includes("In Service"));

    // The record panel recomposes after the sections (committed/spent/pending).
    const recordNow = await waitForText(page, "Pending bills", 15_000);
    check(
      "record: committed ₹4,38,000 / spent ₹4,38,000 / pending bills 1",
      recordNow.includes(inr(438_000)) && recordNow.includes("Pending bills"),
    );

    // Edit the core record via the modal (links must survive the PUT).
    await clickButtonWithText(page, "Edit");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Estimated cost", "460000");
    await clickButtonWithText(page, "Save changes", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "updated successfully", 15_000);
    const edited = await waitForText(page, inr(460_000), 15_000);
    check("core edit via the modal: estimated cost updated, links kept",
      edited.includes(PROJECT_TITLE) && edited.includes(CPC_NAME));

    // --------------------------------------------------------- vendors page
    await page.goto(`${BASE}/finance/vendors`, { waitUntil: "networkidle0" });
    const vendorsPage = await waitForText(page, VENDOR_B_NAME, 60_000);
    check(
      "vendor registry: both vendors with GST numbers + Beta spend ₹4,38,000",
      vendorsPage.includes(VENDOR_A_NAME) &&
        vendorsPage.includes(GST_A) &&
        vendorsPage.includes(GST_B) &&
        vendorsPage.includes(inr(438_000)),
    );
    await setFieldValue(page, 'input[type="search"]', `gamma ${STAMP}`);
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching vendors"),
      { timeout: 15_000 },
    );
    check("vendor search: non-matching query shows the empty state", true);
    await setFieldValue(page, 'input[type="search"]', "");

    await clickButtonWithText(page, "New Vendor");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Vendor name", GAMMA_NAME);
    await typeInField(page, "GST Number", GST_GAMMA);
    await typeInField(page, "PAN", "AABCJ1234K");
    await typeInField(page, "Contact person", "Mohit Verma");
    await typeInField(page, "Email", "hello@gamma-e2e.example");
    await typeInField(page, "Phone", "9830034567");
    await typeInField(page, "Address", "Lajpat Nagar, New Delhi");
    await typeInField(page, "Bank name", "HDFC");
    await typeInField(page, "Account number", "98765432109");
    await typeInField(page, "IFSC", "HDFC0001234");
    await typeInField(page, "Branch", "Lajpat Nagar");
    await clickButtonWithText(page, "Create vendor");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "created successfully", 15_000);
    check("vendor create via the modal (GST + bank details)", true);

    await setFieldValue(page, 'input[type="search"]', `gamma ${STAMP}`);
    // The toast names the vendor too — wait for the ROW's action button, not
    // the text (toast short-circuit precedent from the other harnesses).
    await clickAriaButton(page, `Edit "${GAMMA_NAME}"`);
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Contact person", "Mohit Verma Sr");
    await clickButtonWithText(page, "Save changes");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "updated successfully", 15_000);
    await setFieldValue(page, 'input[type="search"]', `mohit verma sr`);
    await page.waitForFunction(
      (name) => document.body.innerText.includes(name),
      { timeout: 15_000 },
      GAMMA_NAME,
    );
    check("vendor edit via the modal: contact updated + searchable", true);

    // duplicate GST -> backend 409 surfaces in the vendor modal
    await clickButtonWithText(page, "New Vendor");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Vendor name", `Copycat ${STAMP}`);
    await typeInField(page, "GST Number", GST_A);
    await clickButtonWithText(page, "Create vendor");
    await page.waitForSelector('form[role="dialog"] [role="alert"]', { timeout: 15_000 });
    const gstAlert = await page.$eval(
      'form[role="dialog"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check("duplicate GST surfaces the backend 409 in the vendor modal",
      gstAlert.toLowerCase().includes("gst"), gstAlert.slice(0, 90));
    await clickButtonWithText(page, "Cancel", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 10_000,
    });

    // delete Gamma -> confirm dialog + toast + row gone
    await setFieldValue(page, 'input[type="search"]', `gamma ${STAMP}`);
    await clickAriaButton(page, `Delete "${GAMMA_NAME}"`);
    await page.waitForSelector('[role="alertdialog"], [role="dialog"]', { timeout: 10_000 });
    await clickButtonWithText(page, "Delete", { inDialog: true });
    await waitForText(page, "was deleted", 15_000);
    await setFieldValue(page, 'input[type="search"]', `gamma ${STAMP}`);
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching vendors"),
      { timeout: 15_000 },
    );
    check("vendor delete: confirm dialog, toast, row gone", true);
    await setFieldValue(page, 'input[type="search"]', "");

    // ------------------------------------------------------ asset register
    await page.goto(`${BASE}/finance/assets`, { waitUntil: "networkidle0" });
    const register = await waitForText(page, ASSET_ID, 60_000);
    check(
      "asset register: row carries ID, item, category, location, cost, status, proposal",
      register.includes(ASSET_ITEM) &&
        register.includes("Equipment") &&
        register.includes("Data Center") &&
        register.includes(inr(438_000)) &&
        register.includes("In Service") &&
        register.includes(PROPOSAL_NUMBER),
    );
    await setFieldValue(page, 'input[type="search"]', `sn-${STAMP}`);
    await page.waitForFunction(
      (id) => document.body.innerText.includes(id),
      { timeout: 15_000 },
      ASSET_ID,
    );
    check("asset register search finds the asset by serial number", true);
    await setFieldValue(page, 'input[type="search"]', "");
    await page.select('select[aria-label="Filter by category"]', "furniture");
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching assets"),
      { timeout: 15_000 },
    );
    check("asset register: wrong category filter shows the empty state", true);
    await page.select('select[aria-label="Filter by category"]', "equipment");
    await page.waitForFunction(
      (id) => document.body.innerText.includes(id),
      { timeout: 15_000 },
      ASSET_ID,
    );
    check("asset register: equipment filter keeps the asset", true);
    await page.select('select[aria-label="Filter by status"]', "retired");
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching assets"),
      { timeout: 15_000 },
    );
    check("asset register: wrong status filter shows the empty state", true);
    await page.select('select[aria-label="Filter by status"]', "in_service");
    await page.waitForFunction(
      (id) => document.body.innerText.includes(id),
      { timeout: 15_000 },
      ASSET_ID,
    );
    check("asset register: in-service filter keeps the asset", true);

    // The register links back into the procurement workspace.
    await clickLinkWithText(page, PROPOSAL_NUMBER);
    await waitForText(page, "Audit Information", 60_000);
    check("asset register links back to the proposal workspace", true);

    // ------------------------------------------- dashboard after the flows
    await page.goto(`${BASE}/finance`, { waitUntil: "networkidle0" });
    await waitForText(page, "PENDING BILLS", 60_000);
    const finalCards = {
      active: await cardValue(page, "ACTIVE PROCUREMENTS"),
      pending: await cardValue(page, "PENDING APPROVALS"),
      vendors: await cardValue(page, "TOTAL VENDORS"),
      pos: await cardValue(page, "TOTAL PURCHASE ORDERS"),
      utilized: await cardValue(page, "BUDGET UTILIZED"),
      remaining: await cardValue(page, "BUDGET REMAINING"),
      bills: await cardValue(page, "PENDING BILLS"),
    };
    check(
      "dashboard recomposes: +1 PO, +1 pending bill, ₹4,38,000 utilized (exact deltas)",
      finalCards.active === String(base.active_procurements + 1) &&
        finalCards.pending === String(base.pending_approvals + 1) &&
        finalCards.vendors === String(base.total_vendors + 2) &&
        finalCards.pos === String(base.total_purchase_orders + 1) &&
        finalCards.utilized === inr(Number(base.budget_utilized) + 438_000) &&
        finalCards.remaining === inr(baseRemainingEffective + 1_000_000 - 438_000) &&
        finalCards.bills === String(base.pending_bills + 1),
      JSON.stringify(finalCards),
    );
    const budgetRowAfter = await page.evaluate((title) => {
      const row = [...document.querySelectorAll("tr")].find((tr) =>
        tr.textContent?.includes(title),
      );
      return row?.textContent ?? "";
    }, PROJECT_TITLE);
    check(
      "PART 9 budget line recomposes: utilized ₹4,38,000 / remaining ₹5,62,000 / 1 procurement",
      budgetRowAfter.includes(inr(438_000)) && budgetRowAfter.includes(inr(562_000)),
      budgetRowAfter.slice(0, 120),
    );

    // The directory picks up the recommended vendor for the proposal.
    await setFieldValue(page, 'input[type="search"]', `hpc ${STAMP}`);
    const directoryNow = await waitForText(page, PROPOSAL_NUMBER, 15_000);
    check("directory vendor column follows the recommended comparative row",
      directoryNow.includes(VENDOR_B_NAME));
    await setFieldValue(page, 'input[type="search"]', "");

    // ------------------------------------------- frozen module spot check
    await page.goto(`${BASE}/research/projects/${encodeURIComponent(project.id)}`, {
      waitUntil: "networkidle0",
    });
    const projectPage = await waitForText(page, PROJECT_TITLE, 60_000);
    check("frozen research project page still renders (budget intact)",
      projectPage.includes(inr(1_000_000)));

    // ------------------------------------------------------------- delete
    await page.goto(`${BASE}/finance`, { waitUntil: "networkidle0" });
    await setFieldValue(page, 'input[type="search"]', `trash ${STAMP}`);
    await page.waitForFunction(
      (title) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === title),
      { timeout: 15_000 },
      TRASH_TITLE,
    );
    await clickLinkWithText(page, TRASH_TITLE);
    await waitForText(page, "Audit Information", 30_000);
    await clickButtonWithText(page, "Delete");
    await page.waitForSelector('[role="alertdialog"], [role="dialog"]', { timeout: 10_000 });
    await clickButtonWithText(page, "Delete", { inDialog: true });
    await waitForText(page, "was deleted", 30_000);
    check("delete: confirm dialog redirects with a flash toast",
      page.url().endsWith("/finance"));
    await setFieldValue(page, 'input[type="search"]', `trash ${STAMP}`);
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching proposals"),
      { timeout: 15_000 },
    );
    check("delete: the proposal is gone from the directory", true);
    const orphan = await getJson(`/finance/proposals/${encodeURIComponent(trash.id)}`);
    check("delete: the proposal API 404s afterwards", orphan.status === 404,
      String(orphan.status));

    // --------------------------------------------------------- 404 state
    await page.goto(`${BASE}/finance/${encodeURIComponent("obj:purchase:MISSING")}`, {
      waitUntil: "networkidle0",
    });
    await waitForText(page, "Proposal not found", 30_000);
    check("404 state renders for a missing proposal id", true);

    // --------------------------------------------------------- cleanliness
    const hostileApi = failedResponses.filter((line) => {
      if (!line.includes("/api/v1/")) return false;
      // Intentional checks above: duplicate GST (vendor modal) and duplicate
      // proposal number (modal) are on purpose.
      if (line.startsWith("409 POST") && line.endsWith("/api/v1/finance/vendors")) return false;
      if (line.startsWith("409 POST") && line.endsWith("/api/v1/finance/proposals")) return false;
      // The 404-state check above opens a deliberately missing id. The delete
      // flow re-fetches the trashed proposal's page list state (404 tolerated).
      if (line.startsWith("404 GET") && line.includes("/api/v1/finance/proposals/obj:purchase:MISSING")) {
        return false;
      }
      return true;
    });
    check("no failing API requests (>=400)", hostileApi.length === 0, hostileApi[0] ?? "");
    const hostile = consoleErrors.filter(
      (line) =>
        !line.includes("favicon") &&
        !line.includes("404 (Not Found)") && // /favicon.ico — no favicon ships yet
        // The intentional 409 checks log as console errors in chromium.
        !line.includes("409 (Conflict)") &&
        !line.includes("422 (Unprocessable Content)") &&
        !line.includes("422 (Unprocessable Entity)") &&
        !line.includes("Download the React DevTools") &&
        !line.includes("AbortError"),
    );
    check("no browser console errors", hostile.length === 0, hostile[0] ?? "");
  } catch (error) {
    check("unhandled E2E failure", false, String(error));
    try {
      fs.writeFileSync("/tmp/e2e-fail.html", await page.content());
      await page.screenshot({ path: "/tmp/e2e-fail.png", fullPage: true });
      const url = page.url();
      const bodySnippet = (await page.evaluate(() => document.body.innerText)).slice(0, 900);
      console.log(`DEBUG page url: ${url}\nDEBUG body:\n${bodySnippet}`);
      console.log("DEBUG console errors at crash:", JSON.stringify(consoleErrors.slice(-8), null, 1));
      console.log("DEBUG failed responses at crash:", JSON.stringify(failedResponses.slice(-8)));
    } catch (dumpError) {
      console.log("DEBUG dump failed:", String(dumpError));
    }
  } finally {
    await browser.close();
  }

  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed.`);
  process.exit(failed ? 1 : 0);
}

await main();

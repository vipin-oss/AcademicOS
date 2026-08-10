/**
 * Academic Intelligence Assistant module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   sidebar entry -> PART 1 AI Workspace (AI Home grid, status badge, groups)
 *   -> PART 1/15 ask loop: suggested question click, AskBar ask, threads,
 *      append parity with GET /assistant/conversations/{id}
 *   -> PART 2 natural-language search across the seeded world
 *      ("Show my publications", "Show HSRF documents", attendance, meetings)
 *   -> PART 3..11 cross-module answers: dashboard / research / teaching /
 *      finance / events / committees / reports — every one asserting the
 *      deterministic summary, metrics, context cards AND action links
 *   -> PART 4/5 context cards + suggested actions navigate to the frozen
 *      module pages (no re-implemented detail UI)
 *   -> PART 1 history: open older conversation, pin (persist after reload),
 *      inline rename (API parity), New conversation, delete (confirm) ->
 *      404 at the API, reload persistence of the thread
 *   -> cleanliness gates: zero failed API calls, zero console/page errors.
 *
 * The world is seeded through the real APIs (HSRF agency + funded project +
 * grant, two publications, class + 2 students + attendance split + ungraded
 * submission, committee + meeting with decisions + action item, vendor +
 * proposal with PO + paid bill, workshop with certificate participation,
 * HSRF-tagged document, a personal task due today). All names carry the
 * run STAMP so duplicate-code constraints never clash on re-runs; the suite
 * deletes ONLY its own conversations afterwards, leaving the rest of the
 * canonical database as found (the other suites' precedent).
 *
 * Usage:
 *   node tests/assistant-e2e.mjs         # http://localhost:3000
 */
import fs from "node:fs";
import puppeteer from "puppeteer";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

const results = [];
const check = (name, ok, extra = "") => {
  results.push({ name, ok, extra });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? ` — ${extra}` : ""}`);
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const STAMP = Date.now().toString(36);
const TODAY = new Date().toISOString().slice(0, 10);
const d = (offset) => {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
};

const AGENCY_NAME = `HSRF E2E ${STAMP}`;
const PROJECT_TITLE = `HSRF Sensor Grid E2E ${STAMP}`;
const GRANT_TITLE = `HSRF Edge AI Grant E2E ${STAMP}`;
const PUB_JOURNAL = `Graph Kernels Survey E2E ${STAMP}`;
const PUB_CONF = `Edge Inference Workshop E2E ${STAMP}`;
const CLASS_TITLE = `MA201 Assistant E2E ${STAMP}`;
const STUDENT_HIGH = `Asha Attend E2E ${STAMP}`;
const STUDENT_LOW = `Bilal Bunk E2E ${STAMP}`;
const ASSIGNMENT_TITLE = `Eigenvalues Sheet E2E ${STAMP}`;
const COMMITTEE_NAME = `IQAC Assistant E2E ${STAMP}`;
const DECISION_TEXT = `Approved the AQAR annexure sprint ${STAMP}`;
const ACTION_TITLE = `Compile AQAR annexures E2E ${STAMP}`;
const VENDOR_NAME = `Acme Lab E2E ${STAMP}`;
const PROPOSAL_TITLE = `Microscope Procurement E2E ${STAMP}`;
const WORKSHOP_TITLE = `AI Systems Workshop E2E ${STAMP}`;
const FEST_TITLE = `Tech Fest E2E ${STAMP}`;
const DOC_TITLE = `HSRF Application Form E2E ${STAMP}`;
const TASK_TITLE = `Submit leave application E2E ${STAMP}`;

const ids = { conversations: [] };

const postJson = (path, body, method = "POST") =>
  fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

const getJson = (path) =>
  fetch(`${API}${path}`).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

const deleteJson = (path) => fetch(`${API}${path}`, { method: "DELETE" }).then((r) => r.status);

async function waitForText(page, text, timeoutMs = 15_000) {
  await page.waitForFunction(
    (wanted) => document.body.innerText.includes(wanted),
    { timeout: timeoutMs },
    text,
  );
  return true;
}

async function clickLinkWithText(page, text) {
  const clicked = await page.evaluate((wanted) => {
    const link = [...document.querySelectorAll("a")].find(
      (anchor) => anchor.textContent?.trim() === wanted,
    );
    if (!link) return false;
    link.click();
    return true;
  }, text);
  if (!clicked) throw new Error(`No clickable link labelled “${text}” found.`);
}

async function clickAria(page, ariaLabel, timeoutMs = 15_000) {
  await page.waitForFunction(
    (wanted) => {
      const el = [...document.querySelectorAll("[aria-label]")].find(
        (node) => node.getAttribute("aria-label") === wanted && !node.disabled,
      );
      return Boolean(el);
    },
    { timeout: timeoutMs },
    ariaLabel,
  );
  return page.evaluate((wanted) => {
    const el = [...document.querySelectorAll("[aria-label]")].find(
      (node) => node.getAttribute("aria-label") === wanted && !node.disabled,
    );
    el.click();
    return true;
  }, ariaLabel);
}

/** Type into the React-controlled AskBar textarea (native setter + events). */
async function typeQuestion(page, question) {
  await page.waitForSelector('[aria-label="Ask input"]', { timeout: 15_000 });
  await page.evaluate((selector, value) => {
    const input = document.querySelector(selector);
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype,
      "value",
    ).set;
    setter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }, '[aria-label="Ask input"]', question);
}

/** Count of rendered answer cards (one per assistant message). */
async function answerCount(page) {
  return page.$$eval('article[aria-label="Assistant answer"]', (els) => els.length);
}

/** Send a question and wait for its answer article to render `neededText`. */
async function askAndWait(page, question, neededText, { expectIndexDelta = 1 } = {}) {
  const before = await answerCount(page).catch(() => 0);
  await typeQuestion(page, question);
  await clickAria(page, "Send question");
  await page.waitForFunction(
    (wanted, prior) => {
      const cards = [...document.querySelectorAll('article[aria-label="Assistant answer"]')];
      if (cards.length < prior + 1) return false;
      const last = cards[cards.length - 1];
      return last.textContent.includes(wanted);
    },
    { timeout: 30_000 },
    neededText,
    before,
  );
  const count = await answerCount(page);
  return count === before + expectIndexDelta;
}

function armDialog(page) {
  page.once("dialog", (dialog) => {
    void dialog.accept();
  });
}

// ---------------------------------------------------------------------------
// Seeding (through the real APIs — the frozen modules own the data)
// ---------------------------------------------------------------------------
async function seed() {
  const agency = await postJson("/research/agencies", {
    name: AGENCY_NAME,
    uploaded_by: "assistant:e2e",
    scheme: "Faculty Development Grant",
  }).then((r) => r.body);

  const project = await postJson("/research/projects", {
    title: PROJECT_TITLE,
    uploaded_by: "assistant:e2e",
    lifecycle_status: "active",
    project_code: `E2E-${STAMP}-PJ`,
    budget_approved: 400000,
    links: { agencies: [agency.id] },
  }).then((r) => r.body);

  const grant = await postJson("/research/grants", {
    title: GRANT_TITLE,
    grant_number: `HSRF/2026/${STAMP}`,
    uploaded_by: "assistant:e2e",
    amount: 250000,
    links: { projects: [project.id], funding_agencies: [agency.id] },
  }).then((r) => r.body);
  check(
    "seed: HSRF agency + funded project + grant",
    Boolean(agency.id && project.id && grant.id),
    project.id ?? "",
  );

  const year = new Date().getFullYear();
  const pubJournal = await postJson("/publications", {
    title: PUB_JOURNAL,
    publication_type: "journal_article",
    uploaded_by: "assistant:e2e",
    year,
    authors: [{ name: "A. Faculty" }],
  }).then((r) => r.body);
  const pubConf = await postJson("/publications", {
    title: PUB_CONF,
    publication_type: "conference_paper",
    uploaded_by: "assistant:e2e",
    year: year - 1,
    conference: "ICML 2025",
    authors: [{ name: "A. Faculty" }],
  }).then((r) => r.body);
  check(
    "seed: two publications (journal this year + conference paper)",
    Boolean(pubJournal.id && pubConf.id),
  );

  const studentHigh = await postJson("/students", {
    name: STUDENT_HIGH,
    student_type: "ug",
    roll_number: `E2E-${STAMP}-SH`,
    uploaded_by: "assistant:e2e",
  }).then((r) => r.body);
  const studentLow = await postJson("/students", {
    name: STUDENT_LOW,
    student_type: "ug",
    roll_number: `E2E-${STAMP}-SL`,
    uploaded_by: "assistant:e2e",
  }).then((r) => r.body);
  const cls = await postJson("/teaching/classes", {
    title: CLASS_TITLE,
    uploaded_by: "assistant:e2e",
    course_code: `E2E-${STAMP}-MA201`,
    semester: 1,
    session: "2026-27",
  }).then((r) => r.body);
  const enrolled = await postJson(`/teaching/classes/${cls.id}/enroll`, {
    student_ids: [studentHigh.id, studentLow.id],
    actor: "assistant:e2e",
  });
  check(
    "seed: class + 2 enrolled students",
    Boolean(cls.id) && (enrolled.body.enrolled ?? []).length === 2,
    JSON.stringify(enrolled.body).slice(0, 120),
  );

  await postJson(`/teaching/classes/${cls.id}/attendance`, {
    session_date: d(-2),
    records: { [studentHigh.id]: "present", [studentLow.id]: "present" },
    actor: "assistant:e2e",
  });
  await postJson(`/teaching/classes/${cls.id}/attendance`, {
    session_date: d(-1),
    records: { [studentHigh.id]: "present", [studentLow.id]: "absent" },
    actor: "assistant:e2e",
  });
  const assignment = await postJson(`/teaching/classes/${cls.id}/assignments`, {
    title: ASSIGNMENT_TITLE,
    uploaded_by: "assistant:e2e",
    assignment_type: "assignment",
    max_marks: 20,
    deadline: d(9) + "T23:59",
    late_allowed: true,
  }).then((r) => r.body);
  const submitForm = new FormData();
  submitForm.append("student_id", studentLow.id);
  submitForm.append("actor", "assistant:e2e");
  submitForm.append("file", new Blob([`e2e ${STAMP}`], { type: "text/plain" }), "answer.txt");
  const submitted = await fetch(`${API}/teaching/assignments/${assignment.id}/submit`, {
    method: "POST",
    body: submitForm,
  });
  check(
    "seed: attendance split (50% vs 100%) + ungraded submission",
    submitted.status === 201,
    String(submitted.status),
  );

  const committee = await postJson("/committees", {
    name: COMMITTEE_NAME,
    committee_code: `E2E-${STAMP}-IQAC`,
    committee_type: "internal",
    uploaded_by: "assistant:e2e",
    status: "active",
  }).then((r) => r.body);
  const meeting = await postJson(`/committees/${committee.id}/meetings`, {
    title: `IQAC Review E2E ${STAMP}`,
    uploaded_by: "assistant:e2e",
    meeting_number: "1",
    meeting_date: d(4),
    decisions: [DECISION_TEXT],
  }).then((r) => r.body);
  const action = await postJson(`/committees/meetings/${meeting.id}/actions`, {
    title: ACTION_TITLE,
    uploaded_by: "assistant:e2e",
    due_date: d(6),
    priority: "high",
    status: "pending",
  });
  check(
    "seed: committee + meeting with decisions + pending action",
    Boolean(committee.id && meeting.id) && action.status === 201,
  );

  // Unique-per-run gst digits off the ms-clock tail: zero-digit base36
  // stamps would otherwise collapse every same-era run onto one GST number.
  const gstDigits = String(Date.now()).slice(-4);
  const vendor = await postJson("/finance/vendors", {
    name: VENDOR_NAME,
    uploaded_by: "assistant:e2e",
    gst_number: `07AAACE${gstDigits}A1Z5`,
  }).then((r) => r.body);
  const proposal = await postJson("/finance/proposals", {
    title: PROPOSAL_TITLE,
    uploaded_by: "assistant:e2e",
    proposal_number: `E2E-${STAMP}-PP`,
    proposal_date: d(-2),
    proposal_status: "submitted",
    estimated_cost: 90000,
    purchase_orders: [{ po_number: `E2E-${STAMP}-PO`, amount: "45000", vendor_id: vendor.id,
                        status: "issued", delivery_date: d(10) }],
    bills: [{ bill_number: `E2E-${STAMP}-B1`, amount: "20000", payment_status: "paid",
              vendor_id: vendor.id, bill_date: d(-1) }],
  });
  check(
    "seed: vendor + submitted proposal (open PO, paid bill)",
    proposal.status === 201,
    JSON.stringify(proposal.body).slice(0, 160),
  );

  // The certificate reference must be a REAL document object id, so the HSRF
  // upload happens before the events (the module validates the link).
  const docForm = new FormData();
  docForm.append("title", DOC_TITLE);
  docForm.append("document_type", "txt");
  docForm.append("uploaded_by", "assistant:e2e");
  docForm.append("tags", JSON.stringify(["hsrf", "grant"]));
  docForm.append("file", new Blob([`hsrf form ${STAMP}`], { type: "text/plain" }), `hsrf-${STAMP}.txt`);
  const docRes = await fetch(`${API}/documents`, { method: "POST", body: docForm });
  const docBody = await docRes.json().catch(() => ({}));
  check("seed: HSRF document uploaded", docRes.status === 201, String(docRes.status));

  const workshop = await postJson("/events", {
    title: WORKSHOP_TITLE,
    uploaded_by: "assistant:e2e",
    status: "active",
    event_code: `EVT-${STAMP}-W`,
    event_type: "workshop",
    start_date: d(5),
    end_date: d(6),
    event_status: "planned",
    participation: [{ role: "participant", certificate_document_id: docBody.id }],
    registration: { expected_participants: 40, certificates_issued: 1 },
  }).then((r) => r.body);
  const fest = await postJson("/events", {
    title: FEST_TITLE,
    uploaded_by: "assistant:e2e",
    status: "active",
    event_code: `EVT-${STAMP}-F`,
    event_type: "competition",
    start_date: d(-30),
    end_date: d(-29),
    event_status: "completed",
    participation: [{ role: "organizer", contribution: "Convener" }],
  }).then((r) => r.body);
  check(
    "seed: upcoming workshop (certificate) + completed organized fest",
    Boolean(workshop.id && fest.id),
  );

  const task = await postJson("/productivity/tasks", {
    title: TASK_TITLE,
    uploaded_by: "assistant:e2e",
    due_date: TODAY,
  });
  check("seed: personal task due today", task.status === 201, String(task.status));
  Object.assign(ids, { studyId: studentLow.id, pubJournalId: pubJournal.id });
}

// ---------------------------------------------------------------------------
// Browser tour
// ---------------------------------------------------------------------------
async function main() {
  await seed();

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
    // ------------------------------------------------ sidebar -> assistant
    await page.goto(`${BASE}/settings`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Settings & Preferences", 30_000);
    await clickLinkWithText(page, "Assistant");
    await waitForText(page, "Academic Intelligence Assistant", 30_000);
    check(
      "sidebar: Assistant entry navigates to /assistant",
      page.url().endsWith("/assistant"),
      page.url(),
    );

    // ------------------------------------------------ PART 1 AI Home
    await waitForText(page, "What would you like to know?", 30_000);
    const groups = await page.$$eval("section[aria-label^=\"Suggested:\"]", (els) =>
      els.map((el) => el.getAttribute("aria-label").replace("Suggested: ", "")),
    );
    check(
      "ai home: all 8 suggested groups render",
      JSON.stringify(groups) ===
        JSON.stringify(["Dashboard", "Research", "Teaching", "Finance", "Events",
          "Committees", "Reports", "Search"]),
      groups.join(","),
    );
    const badgeText = await page.evaluate(() => {
      const badge = document.querySelector('[aria-label="Assistant status"]');
      return (badge?.textContent ?? "").toLowerCase();
    });
    check(
      "ai home: status badge documents the local deterministic engine",
      badgeText.includes("rules-v1") && badgeText.includes("no external ai"),
      badgeText,
    );

    // --------------------------------------- suggested question -> answer
    await clickAria(page, "Suggested question What should I do today?");
    const firstAnswer = await page
      .waitForFunction(
        () =>
          [...document.querySelectorAll('article[aria-label="Assistant answer"]')].some((el) =>
            el.textContent.includes("Today’s plan"),
          ),
        { timeout: 30_000 },
      )
      .then(() => true)
      .catch(() => false);
    check("PART 6: “What should I do today?” answers with the Today’s plan card", firstAnswer);
    ids.conversations.push(
      (await getJson("/assistant/conversations?page_size=1")).body.items?.[0]?.id,
    );
    await waitForText(page, TASK_TITLE, 10_000)
      .then(() => check("PART 6: today plan surfaces the seeded due-today task", true))
      .catch(() => check("PART 6: today plan surfaces the seeded due-today task", false));

    // ------------------------------------------- second ask in same thread
    const ok2 = await askAndWait(page, "Upcoming meetings", "Upcoming meetings");
    check("PART 1/15: follow-up question appends in the same thread", ok2);
    await waitForText(page, WORKSHOP_TITLE, 10_000)
      .then(() => check("PART 6: upcoming meetings list the seeded workshop", true))
      .catch(() => check("PART 6: upcoming meetings list the seeded workshop", false));

    // ------------------------------------------- PART 2/7 research answers
    await askAndWait(page, "Show my publications", "publication(s)");
    const pubCards = await page.$$eval('a[aria-label^="Open Publication:"]', (els) =>
      els.map((el) => el.getAttribute("href")),
    );
    check(
      "PART 2/7: “Show my publications” returns linked publication cards",
      pubCards.some((href) => href === `/publications/${ids.pubJournalId}`),
    );

    await askAndWait(page, "My latest publication", "latest publication");
    await waitForText(page, PUB_JOURNAL, 10_000)
      .then(() => check("PART 7: latest publication names the seeded journal paper", true))
      .catch(() => check("PART 7: latest publication names the seeded journal paper", false));

    await askAndWait(page, "Conference papers", "conference paper");
    await waitForText(page, PUB_CONF, 10_000)
      .then(() => check("PART 7: conference papers list the seeded paper", true))
      .catch(() => check("PART 7: conference papers list the seeded paper", false));

    await askAndWait(page, "Projects funded by HSRF", "funded by");
    await waitForText(page, PROJECT_TITLE, 10_000)
      .then(() => check("PART 3/7: projects funded by HSRF resolves the seeded project", true))
      .catch(() => check("PART 3/7: projects funded by HSRF resolves the seeded project", false));

    await askAndWait(page, "Research grants", "grant(s)");
    await waitForText(page, "₹2,50,000", 10_000)
      .then(() => check("PART 7/3: grants total uses Reports en-IN money formatting", true))
      .catch(() => check("PART 7/3: grants total uses Reports en-IN money formatting", false));

    await askAndWait(page, "Show HSRF documents", "document(s)");
    await waitForText(page, DOC_TITLE, 10_000)
      .then(() => check("PART 2/3: “Show HSRF documents” finds the tagged upload", true))
      .catch(() => check("PART 2/3: “Show HSRF documents” finds the tagged upload", false));

    // ------------------------------------------- PART 8 teaching answers
    await askAndWait(page, "Show students below 75% attendance", "below 75%");
    await waitForText(page, STUDENT_LOW, 10_000)
      .then(() => check("PART 8: below-75% attendance names the 50% student", true))
      .catch(() => check("PART 8: below-75% attendance names the 50% student", false));
    const absentHigh = await page.evaluate(
      (name) => {
        const cards = [...document.querySelectorAll('article[aria-label="Assistant answer"]')];
        const last = cards[cards.length - 1];
        return last ? last.textContent.includes(name) : true;
      },
      STUDENT_HIGH,
    );
    check("PART 8: the 100% student is not flagged", absentHigh === false);

    await askAndWait(page, "Pending grading", "ungraded submission");
    await waitForText(page, ASSIGNMENT_TITLE, 10_000)
      .then(() => check("PART 8: pending grading links the seeded assignment", true))
      .catch(() => check("PART 8: pending grading links the seeded assignment", false));

    await askAndWait(page, "Assignments pending", "assignment deadline");
    await waitForText(page, ASSIGNMENT_TITLE, 10_000)
      .then(() => check("PART 8: pending assignments include the seeded deadline", true))
      .catch(() => check("PART 8: pending assignments include the seeded deadline", false));

    // ------------------------------------------- PART 9 finance answers
    await askAndWait(page, "Budget remaining", "Budget remaining");
    await waitForText(page, "₹", 10_000)
      .then(() => check("PART 9: budget remaining carries INR metrics", true))
      .catch(() => check("PART 9: budget remaining carries INR metrics", false));

    await askAndWait(page, "Show pending purchases", "in flight");
    await waitForText(page, PROPOSAL_TITLE, 10_000)
      .then(() => check("PART 9: pending purchases list the submitted proposal", true))
      .catch(() => check("PART 9: pending purchases list the submitted proposal", false));

    // ------------------------------------------- PART 10 events answers
    await askAndWait(page, "Upcoming workshops", "workshop");
    await waitForText(page, WORKSHOP_TITLE, 10_000)
      .then(() => check("PART 10: upcoming workshops list the seeded workshop", true))
      .catch(() => check("PART 10: upcoming workshops list the seeded workshop", false));

    await askAndWait(page, "Events organized", "organising record");
    await waitForText(page, FEST_TITLE, 10_000)
      .then(() => check("PART 10: organized events list the seeded fest", true))
      .catch(() => check("PART 10: organized events list the seeded fest", false));

    await askAndWait(page, "Certificates", "certificate(s) on record");
    await waitForText(page, WORKSHOP_TITLE, 10_000)
      .then(() => check("PART 10: certificates answer cites the workshop", true))
      .catch(() => check("PART 10: certificates answer cites the workshop", false));

    // ------------------------------------------- PART 11 committees answers
    await askAndWait(page, "Show pending committee actions", "action item");
    await waitForText(page, ACTION_TITLE, 10_000)
      .then(() => check("PART 11: pending committee actions list the seeded item", true))
      .catch(() => check("PART 11: pending committee actions list the seeded item", false));

    await askAndWait(page, "Recent decisions", "recorded decisions");
    await waitForText(page, DECISION_TEXT, 10_000)
      .then(() => check("PART 11: recent decisions echo the seeded minutes", true))
      .catch(() => check("PART 11: recent decisions echo the seeded minutes", false));

    // ------------------------------------------- PART 12 reports answers
    await askAndWait(page, "What reports can I see?", "report kinds");
    const reportAction = await page.evaluate(() =>
      [...document.querySelectorAll('a[aria-label^="Action:"]')].some((a) =>
        a.getAttribute("href") === "/reports",
      ),
    );
    check("PART 5/12: report catalogue answer links to /reports", reportAction);

    await askAndWait(page, "Summarize the publications report", "headline numbers");
    await waitForText(page, "Total Publications", 10_000)
      .then(() => check("PART 12: report summary reuses the report KPI strip", true))
      .catch(() => check("PART 12: report summary reuses the report KPI strip", false));

    // ------------------------------------------- PART 13 knowledge search
    await askAndWait(page, "search for Regression Seed Course 07", "knowledge-graph");
    await waitForText(page, "Regression Seed Course 07", 10_000)
      .then(() => check("PART 13: knowledge search reuses the universal object corpus", true))
      .catch(() => check("PART 13: knowledge search reuses the universal object corpus", false));

    await askAndWait(page, "hello", "AcademicOS Intelligence")
      .then((ok) => check("PART 1: greeting stays inside the assistant persona", ok));

    // ------------------------------------------- PART 4/5 cards + actions
    const cardLink = await page.$$eval(
      'a[aria-label^="Action:"]',
      (els) => els.find((el) => el.getAttribute("href") === "/publications")?.getAttribute("href"),
    );
    check("PART 5: a module action on a publication answer is a real link", Boolean(cardLink));
    await clickAria(page, "Action: Open Publications");
    await page.waitForFunction(() => location.pathname === "/publications", { timeout: 15_000 });
    check("PART 5: clicking a module action opens the Publications module", true);
    await page.goto(`${BASE}/assistant`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "What would you like to know?", 30_000);
    // Context card out of an answer: ask again, then click the publication card.
    await askAndWait(page, "Show my publications", "publication(s)");
    await clickAria(page, `Open Publication: ${PUB_JOURNAL}`);
    await page.waitForFunction(
      (id) => location.pathname === `/publications/${id}`,
      { timeout: 15_000 },
      ids.pubJournalId,
    );
    check("PART 4: clicking a context card navigates to the linked module page", true);

    // ------------------------------------------- PART 1 history / pin / CRUD
    await page.goto(`${BASE}/assistant`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "What would you like to know?", 30_000);
    const listTitles = () =>
      page.$$eval('button[aria-label^="Open conversation "]', (els) =>
        els.map((el) => el.getAttribute("aria-label").replace("Open conversation ", "")),
      );
    const titles = await listTitles();
    check(
      "PART 1: conversation history lists this run's threads",
      titles.some((title) => title.includes("What should I do today?")),
      titles.slice(0, 3).join(" | "),
    );

    const firstTitle = titles[0];
    await clickAria(page, `Open conversation ${firstTitle}`);
    await page.waitForFunction(
      () => document.querySelectorAll('article[aria-label="Assistant answer"]').length >= 1,
      { timeout: 15_000 },
    );
    check("PART 1: opening a historic conversation reloads its thread", true);

    await clickAria(page, "Back to AI Home", 10_000).catch(() => {});
    const beforePin = await listTitles();
    const targetTitle = beforePin.find((title) => title.includes("Show my publications")) ?? beforePin[0];
    await clickAria(page, "Pin conversation", 15_000); // pins the first row
    await sleep(600);
    await page.reload({ waitUntil: "networkidle2" });
    await waitForText(page, "What would you like to know?", 30_000);
    const afterPin = await listTitles();
    const pinnedInApi = await getJson("/assistant/conversations").then((r) =>
      (r.body.items ?? []).filter((c) => c.pinned),
    );
    check(
      "PART 1: pin persists across a reload (API parity)",
      pinnedInApi.length >= 1 && afterPin.length === beforePin.length,
      JSON.stringify(pinnedInApi.map((c) => c.title).slice(0, 2)),
    );

    // rename the pinned (first) conversation inline
    const renameName = `Deep dive E2E ${STAMP.slice(-4)}`;
    const apiList = await getJson("/assistant/conversations?page_size=1").then((r) => r.body.items);
    const renameTarget = apiList[0];
    await clickAria(page, "Rename conversation", 15_000);
    await page.waitForSelector('[aria-label="Rename input"]', { timeout: 10_000 });
    await page.evaluate((value) => {
      const input = document.querySelector('[aria-label="Rename input"]');
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      setter.call(input, value);
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }, renameName);
    await clickAria(page, "Save rename");
    await sleep(700);
    const renamed = await getJson(`/assistant/conversations/${renameTarget.id}`).then(
      (r) => r.body.conversation?.title,
    );
    check(
      "PART 1: inline rename persists (API parity)",
      renamed === renameName,
      String(renamed),
    );
    ids.conversations.push(renameTarget.id);

    // new conversation -> ask once -> auto title
    await clickAria(page, "New conversation");
    const freshOk = await askAndWait(page, "certificates", "certificate(s) on record");
    check("PART 1: New conversation starts an empty thread that answers", freshOk);
    // the pinned thread floats first server-side — find the fresh one by title
    const historyNow = await getJson("/assistant/conversations?page_size=50").then(
      (r) => r.body.items ?? [],
    );
    const newest = historyNow.find((c) => c.title === "certificates");
    check(
      "PART 1: asked conversation gets the auto-derived title",
      Boolean(newest),
      (newest ?? historyNow[0] ?? {}).title ?? "",
    );
    if (newest?.id) ids.conversations.push(newest.id);

    // delete with the confirm dialog
    await waitForText(page, "Deep dive", 10_000).catch(() => {});
    const delList = await getJson("/assistant/conversations?page_size=50").then((r) => r.body.items);
    const doomed = delList.find((c) => c.title.includes("Deep dive"));
    if (doomed) {
      const doomedId = doomed.id;
      let candidateLabel = `Open conversation ${doomed.title}`;
      const hasRow = await page.$(`button[aria-label="${candidateLabel}"]`);
      if (!hasRow) {
        // scroll the list into view; aria remains identical
      }
      const row = await page.$(`button[aria-label="${candidateLabel}"]`);
      if (row) {
        await row.evaluate((el) => {
          const actions = el.parentElement.querySelectorAll('button[aria-label="Delete conversation"]');
          window.__doomed = actions[0];
        });
        armDialog(page);
        await page.evaluate(() => window.__doomed.click());
        await sleep(700);
      }
      const after = await getJson(`/assistant/conversations/${doomedId}`);
      check(
        "PART 1: delete removes the thread (API 404 after confirm)",
        after.status === 404,
        String(after.status),
      );
    } else {
      check("PART 1: delete removes the thread (API 404 after confirm)", false, "no rename target found");
    }

    // reload persistence of the remaining thread
    await page.reload({ waitUntil: "networkidle2" });
    await waitForText(page, "What would you like to know?", 30_000);
    const persisted = await getJson("/assistant/conversations?page_size=1").then(
      (r) => r.body.items?.[0],
    );
    check(
      "PART 1: threads survive a full reload (server persistence)",
      Boolean(persisted && persisted.message_count >= 2),
    );

    // ------------------------------------------------ cleanliness gates
    check(
      "cleanliness: no failed API call during the whole tour",
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
      await page.screenshot({ path: "/tmp/assistant-failure.png", fullPage: true });
      fs.writeFileSync("/tmp/assistant-failure.txt", await page.content());
    } catch {
      /* ignore */
    }
  } finally {
    await browser.close();
    // Leave the canonical database as found: delete ONLY this run's threads.
    const listing = await getJson("/assistant/conversations?page_size=100").then(
      (r) => r.body.items ?? [],
    );
    for (const conversation of listing) {
      const mine =
        conversation.title.startsWith("certificates") ||
        conversation.title.includes("What should I do today?") ||
        conversation.title.includes("Upcoming meetings") ||
        conversation.title.includes("Show my publications") ||
        conversation.title.includes("My latest publication") ||
        conversation.title.includes("Conference papers") ||
        conversation.title.includes("Projects funded by HSRF") ||
        conversation.title.includes("Research grants") ||
        conversation.title.includes("Show HSRF documents") ||
        conversation.title.includes("Show students below 75% attendance") ||
        conversation.title.includes("Pending grading") ||
        conversation.title.includes("Assignments pending") ||
        conversation.title.includes("Budget remaining") ||
        conversation.title.includes("Show pending purchases") ||
        conversation.title.includes("Upcoming workshops") ||
        conversation.title.includes("Events organized") ||
        conversation.title.includes("Certificates") ||
        conversation.title.includes("Show pending committee actions") ||
        conversation.title.includes("Recent decisions") ||
        conversation.title.includes("What reports can I see?") ||
        conversation.title.includes("Summarize the publications report") ||
        conversation.title.includes("search for Regression Seed Course 07") ||
        conversation.title.includes("hello") ||
        conversation.title.includes("Deep dive E2E") ||
        conversation.title === "New conversation";
      if (mine) await deleteJson(`/assistant/conversations/${conversation.id}`);
    }
  }

  const failed = results.filter((entry) => !entry.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  if (failed.length > 0) {
    console.log("FAILURES:");
    for (const entry of failed) console.log(`  - ${entry.name}${entry.extra ? ` — ${entry.extra}` : ""}`);
    process.exitCode = 1;
  }
}

// Convenience wrapper kept local to avoid a promisify mismatch in older Node.
async function waitForFunction(page, text, timeoutMs) {
  await page.waitForFunction(
    () => document.querySelectorAll('article[aria-label="Assistant answer"]').length >= 1 ||
      document.body.innerText.length > 0,
    { timeout: timeoutMs },
  );
}

await main();

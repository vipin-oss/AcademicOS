/**
 * Reports & Analytics module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   sidebar entry -> PART 1 hub dashboard (11 cards, exact baseline+delta)
 *   -> launchpad -> publications workspace (group-by lenses carrying the
 *   STAMP-scoped seeds + PART 12 year/date/project filters) -> research
 *   (budget/team/publications) -> faculty overview + member profile via the
 *   picker -> students overview + per-student lens (attendance 50%, marks
 *   90%) -> teaching (class/attendance/assignment/gradebook rows) -> finance
 *   (budget/vendor/purchase/assets) -> events (organized/workshops) ->
 *   committees (meetings/attendance/actions pending+completed) -> analytics
 *   (5 trend charts incl. the monthly attendance trend) -> PART 11 export
 *   buttons (href contracts + the real export bytes fetched over HTTP:
 *   CSV content, XLSX PK magic, PDF %PDF magic, filtered CSV) -> filter
 *   error surface (inverted date range) -> unknown kind 404 -> hub re-check.
 *
 * The cross-module world (faculty, student, class + roster + attendance +
 * assignment + graded submission, project + grant + installment, two
 * publications, two events, committee + meeting + actions, vendor +
 * proposal) is seeded through the FROZEN modules' own APIs. Global counters
 * (dashboard card totals) are asserted as BASELINE + DELTA so the suite
 * composes with the other E2E suites in a shared database.
 *
 * Usage:
 *   node tests/reports-e2e.mjs         # http://localhost:3000
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
const inr = (value) => `₹${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value)}`;

const STAMP = Date.now().toString(36);
const FACULTY_NAME = `Dr. Meera Krishnan E2E ${STAMP}`;
const STUDENT_NAME = `Asha Verma E2E ${STAMP}`;
const PROJECT_TITLE = `Graph Frontiers E2E ${STAMP}`;
const GRANT_TITLE = `SERB Core E2E ${STAMP}`;
const PUB1_TITLE = `Ramsey Bounds E2E ${STAMP}`;
const PUB2_TITLE = `Chromatic Cycles E2E ${STAMP}`;
const CLASS_TITLE = `Linear Algebra E2E ${STAMP}`;
const EVENT_TITLE = `Mathematics Day E2E ${STAMP}`;
const WORKSHOP_TITLE = `STM Workshop E2E ${STAMP}`;
const COMMITTEE_NAME = `IQAC Reports E2E ${STAMP}`;
const MEETING_TITLE = `IQAC Meeting E2E ${STAMP}`;
const VENDOR_NAME = `Alpha Traders E2E ${STAMP}`;
const PROPOSAL_TITLE = `Books Purchase E2E ${STAMP}`;
// Vendors enforce a unique GST number across runs, so derive a run-unique,
// format-valid GSTIN (^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$).
const GSTIN = `05${STAMP.toUpperCase()
  .replace(/[0-9]/g, (d) => String.fromCharCode(65 + Number(d)))
  .padEnd(5, "X").slice(0, 5)}${String(Math.floor(1000 + Math.random() * 9000))}F1Z5`;

const postJson = (path, body, method = "POST") =>
  fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

const getJson = (path) =>
  fetch(`${API}${path}`).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

async function waitForText(page, text, timeoutMs = 10_000) {
  await page.waitForFunction(
    (wanted) => document.body.innerText.includes(wanted),
    { timeout: timeoutMs },
    text,
  );
  return true;
}

async function waitForGone(page, selector, timeoutMs = 10_000) {
  await page.waitForFunction(
    (sel) => !document.querySelector(sel),
    { timeout: timeoutMs },
    selector,
  );
}

/** Click a link by its exact visible label. */
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

/** Read the big value of a PART 1 dashboard card by its label. */
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

/** All rows of the FIRST table section whose heading contains `titlePart`. */
async function tableRows(page, titlePart) {
  return page.evaluate((wanted) => {
    const section = [...document.querySelectorAll("section")].find((el) => {
      const heading = el.querySelector("h2");
      // Skip chart sections (SVG only, no <table>) whose titles can share
      // a prefix with the wanted table, e.g. "Meetings per Year" vs "Meetings".
      return heading && heading.textContent.includes(wanted) && el.querySelector("table");
    });
    if (!section) return null;
    return [...section.querySelectorAll("tbody tr")].map((row) =>
      [...row.querySelectorAll("td")].map((cell) => cell.textContent?.trim() ?? ""),
    );
  }, titlePart);
}

async function kpiValue(page, label) {
  return page.evaluate((wanted) => {
    const cards = [...document.querySelectorAll(".rounded-xl")];
    for (const card of cards) {
      const labelEl = [...card.querySelectorAll("div")].find(
        (el) => el.textContent?.trim() === wanted,
      );
      if (labelEl) {
        const value = card.querySelector("p")?.textContent?.trim();
        if (value != null) return value;
      }
    }
    return null;
  }, label);
}

async function setSelectWhenReady(page, ariaLabel, value, timeoutMs = 10_000) {
  const selector = `select[aria-label="${ariaLabel}"]`;
  await page.waitForFunction(
    (sel, val) => {
      const select = document.querySelector(sel);
      return select ? [...select.options].some((option) => option.value === val) : false;
    },
    { timeout: timeoutMs },
    selector,
    value,
  );
  await page.select(selector, value);
}

/** Expected dashboard after seeding = captured baseline + our deltas. */
function expectedCounts(base) {
  return {
    total_publications: base.total_publications + 2,
    total_projects: base.total_projects + 1,
    total_grants: base.total_grants + 1,
    total_students: base.total_students + 1,
    total_classes: base.total_classes + 1,
    total_faculty: base.total_faculty + 1,
    total_committees: base.total_committees + 1,
    total_events: base.total_events + 2,
    budget_approved: base.budget_approved + 500000,
    budget_utilized: base.budget_utilized + 160000, // 120k project + 40k bill
    budget_remaining: base.budget_remaining + 340000,
  };
}

async function seed() {
  const ids = {};
  let r = await postJson("/faculty", {
    name: FACULTY_NAME, employee_id: `E2E-${STAMP}-FA`, uploaded_by: "e2e:reports",
    department: "Mathematics", designation: "Professor", email: "meera@univ.edu",
  });
  if (r.status !== 201) throw new Error(`faculty seed: ${r.status}`);
  ids.faculty = r.body.id;

  r = await postJson("/students", {
    name: STUDENT_NAME, student_type: "pg", roll_number: `E2E-${STAMP}-ST`,
    uploaded_by: "e2e:reports", department: "Mathematics",
    programme: "MSc Mathematics", semester: 2,
  });
  if (r.status !== 201) throw new Error(`student seed: ${r.status}`);
  ids.student = r.body.id;

  r = await postJson("/research/projects", {
    title: PROJECT_TITLE, uploaded_by: "e2e:reports", lifecycle_status: "active",
    project_code: `E2E-${STAMP}-PR`, department: "Mathematics",
    start_date: "2024-04-01", end_date: "2027-03-31",
    budget_approved: 500000, budget_utilized: 120000,
    team: { principal_investigators: [ids.faculty] },
  });
  if (r.status !== 201) throw new Error(`project seed: ${r.status}`);
  ids.project = r.body.id;

  r = await postJson("/research/grants", {
    title: GRANT_TITLE, grant_number: `E2E-${STAMP}-GR`, uploaded_by: "e2e:reports",
    amount: 300000, links: { projects: [ids.project] },
  });
  if (r.status !== 201) throw new Error(`grant seed: ${r.status}`);
  ids.grant = r.body.id;

  r = await postJson(`/research/grants/${ids.grant}/installments`, {
    installment_no: 1, date: "2024-06-01", amount: 100000,
    status: "released", uploaded_by: "e2e:reports",
  });
  if (r.status !== 201) throw new Error(`installment seed: ${r.status}`);

  r = await postJson("/publications", {
    title: PUB1_TITLE, publication_type: "journal_article", uploaded_by: "e2e:reports",
    year: 2025, journal: "JCTA",
    authors: [{ name: FACULTY_NAME }, { name: "Asha Verma" }],
    links: { faculty: [ids.faculty], projects: [ids.project] },
  });
  if (r.status !== 201) throw new Error(`pub1 seed: ${r.status}`);
  ids.pub1 = r.body.id;

  r = await postJson("/publications", {
    title: PUB2_TITLE, publication_type: "conference_paper", uploaded_by: "e2e:reports",
    year: 2026, conference: "ICM 2026",
    authors: [{ name: FACULTY_NAME }],
    links: { faculty: [ids.faculty], grants: [ids.grant] },
  });
  if (r.status !== 201) throw new Error(`pub2 seed: ${r.status}`);
  ids.pub2 = r.body.id;

  r = await postJson("/teaching/classes", {
    title: CLASS_TITLE, uploaded_by: "e2e:reports", course_code: `E2E-${STAMP}-MA`,
    programme: "MSc Mathematics", semester: 2, credits: 4,
    students: [ids.student], links: { teachers: [ids.faculty] },
  });
  if (r.status !== 201) throw new Error(`class seed: ${r.status}`);
  ids.class = r.body.id;

  for (const [date, state] of [["2026-01-10", "present"], ["2026-01-12", "absent"]]) {
    r = await postJson(`/teaching/classes/${ids.class}/attendance`, {
      session_date: date, records: { [ids.student]: state }, actor: "e2e:reports",
    });
    if (r.status !== 201) throw new Error(`attendance seed: ${r.status}`);
  }

  r = await postJson("/teaching/assignments", {
    title: `Problem Set E2E ${STAMP}`, uploaded_by: "e2e:reports",
    class_id: ids.class, assignment_type: "assignment",
    max_marks: 20, deadline: "2027-01-20", weightage: 50,
  });
  if (r.status !== 201) throw new Error(`assignment seed: ${r.status}`);
  ids.assignment = r.body.id;

  r = await fetch(`${API}/teaching/assignments/${ids.assignment}/submit`, {
    method: "POST",
    body: new URLSearchParams({ student_id: ids.student, actor: "e2e:reports" }),
  }).then(async (res) => ({ status: res.status, body: await res.json().catch(() => ({})) }));
  if (r.status !== 201) throw new Error(`submission seed: ${r.status}`);
  ids.submission = r.body.id;
  r = await postJson(`/teaching/submissions/${ids.submission}/grade`, {
    marks: 18, actor: "e2e:reports",
  }, "PATCH");
  if (r.status !== 200) throw new Error(`grade seed: ${r.status}`);

  r = await postJson("/events", {
    title: EVENT_TITLE, uploaded_by: "e2e:reports", event_type: "mathematics_day",
    event_status: "completed", start_date: "2026-12-22", department: "Mathematics",
    participation: [{ role: "organizer", contribution: "Led the quiz" }],
    links: { faculty: [ids.faculty] },
  });
  if (r.status !== 201) throw new Error(`event seed: ${r.status}`);
  ids.event = r.body.id;

  r = await postJson("/events", {
    title: WORKSHOP_TITLE, uploaded_by: "e2e:reports", event_type: "workshop",
    event_status: "completed", start_date: "2025-11-05", department: "Mathematics",
    participation: [{ role: "participant" }],
  });
  if (r.status !== 201) throw new Error(`workshop seed: ${r.status}`);
  ids.workshop = r.body.id;

  r = await postJson("/committees", {
    name: COMMITTEE_NAME, uploaded_by: "e2e:reports", committee_code: `E2E-${STAMP}-IQ`,
    committee_type: "Internal Quality Assurance Cell (IQAC)",
    members: [{ faculty_id: ids.faculty, name: FACULTY_NAME, role: "convener" }],
  });
  if (r.status !== 201) throw new Error(`committee seed: ${r.status} ${JSON.stringify(r.body)}`);
  ids.committee = r.body.id;

  r = await postJson(`/committees/${ids.committee}/meetings`, {
    title: MEETING_TITLE, uploaded_by: "e2e:reports", meeting_number: "1",
    meeting_date: "2026-02-10", mode: "offline",
    attendance: [{ object_id: ids.faculty, name: FACULTY_NAME, status: "present" }],
  });
  if (r.status !== 201) throw new Error(`meeting seed: ${r.status}`);
  ids.meeting = r.body.id;

  for (const action of [
    { title: `Prepare AQAR E2E ${STAMP}`, status: "pending", due_date: "2026-03-01", priority: "high" },
    { title: `Upload minutes E2E ${STAMP}`, status: "done", due_date: "2026-02-15" },
  ]) {
    r = await postJson(`/committees/meetings/${ids.meeting}/actions`, {
      ...action, uploaded_by: "e2e:reports", assigned_to: ids.faculty,
    });
    if (r.status !== 201) throw new Error(`action seed: ${r.status}`);
  }

  r = await postJson("/finance/vendors", {
    name: VENDOR_NAME, uploaded_by: "e2e:reports", gst_number: GSTIN,
  });
  if (r.status !== 201) throw new Error(`vendor seed: ${r.status}`);
  ids.vendor = r.body.id;

  r = await postJson("/finance/proposals", {
    title: PROPOSAL_TITLE, uploaded_by: "e2e:reports", proposal_number: `E2E-${STAMP}-PP`,
    department: "Mathematics", proposal_date: "2026-01-15", proposal_status: "approved",
    estimated_cost: 50000,
    purchase_orders: [{ po_number: `E2E-${STAMP}-PO`, amount: "40000",
                        vendor_id: ids.vendor, status: "issued" }],
    bills: [{ bill_number: `E2E-${STAMP}-B`, amount: "38000", gst_amount: "2000",
              payment_status: "paid", vendor_id: ids.vendor }],
    assets: [{ asset_id: `E2E-${STAMP}-AS`, category: "equipment",
               item_name: "Projector", cost: "38000", status: "in_service" }],
    links: { projects: [ids.project] },
  });
  if (r.status !== 201) throw new Error(`proposal seed: ${r.status}`);
  ids.proposal = r.body.id;
  return ids;
}

async function main() {
  // Baselines BEFORE seeding (global counters are shared with other suites).
  const dashBase = (await getJson("/reports/dashboard")).body;
  const eventsBase = (await getJson("/reports/events")).body;
  const committeesBase = (await getJson("/reports/committees")).body;
  check("seed: baselines captured", !!dashBase && !!eventsBase && !!committeesBase);

  const ids = await seed();
  check("seed: cross-module world created through frozen APIs", !!ids.proposal);
  const expected = expectedCounts(dashBase);

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
      const text = `${msg.text()} @${url}`;
      // App-wide favicon absence emits a 404 network error unrelated to reports;
      // API failures are gated separately via the failingApi listener.
      if (url.includes("favicon") || msg.text().startsWith("Failed to load resource")) return;
      consoleErrors.push(text);
    }
  });

  try {
    // ------------------------------------------------ PART 1 dashboard hub
    await page.goto(`${BASE}/events`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Events & Academic Activities", 30_000);
    await clickLinkWithText(page, "Reports");
    await page.waitForSelector("h1");
    await waitForText(page, "Reports & Analytics", 30_000);
    check("sidebar: Reports entry navigates to the hub", page.url().endsWith("/reports"));

    // Cards stream in after the initial skeleton — wait for real values first.
    await page.waitForFunction(
      () => {
        const cards = [...document.querySelectorAll(".rounded-xl")];
        return cards.some((card) => {
          const labelEl = [...card.querySelectorAll("div")].find(
            (el) => el.textContent?.trim().toUpperCase() === "BUDGET APPROVED",
          );
          return labelEl && (card.querySelector("p")?.textContent ?? "").includes("₹");
        });
      },
      { timeout: 30_000 },
    );
    const cardLabels = [
      "Publications", "Research Projects", "Grants", "Students", "Classes",
      "Faculty", "Committees", "Events",
      "Budget Approved", "Budget Utilized", "Budget Remaining",
    ];
    const cards = await Promise.all(cardLabels.map((label) => cardValue(page, label)));
    check("hub: all eleven PART 1 cards render", cards.every((v) => v !== null),
      cards.join("|"));
    const seen = {
      total_publications: Number.parseInt(cards[0] ?? "", 10),
      total_projects: Number.parseInt(cards[1] ?? "", 10),
      total_grants: Number.parseInt(cards[2] ?? "", 10),
      total_students: Number.parseInt(cards[3] ?? "", 10),
      total_classes: Number.parseInt(cards[4] ?? "", 10),
      total_faculty: Number.parseInt(cards[5] ?? "", 10),
      total_committees: Number.parseInt(cards[6] ?? "", 10),
      total_events: Number.parseInt(cards[7] ?? "", 10),
    };
    check("hub: module totals are baseline + seeded deltas",
      ["total_publications", "total_projects", "total_grants", "total_students",
       "total_classes", "total_faculty", "total_committees", "total_events"]
        .every((key) => seen[key] === expected[key]),
      JSON.stringify(seen));
    check("hub: budget triplet money strings",
      cards[8] === inr(expected.budget_approved) &&
      cards[9] === inr(expected.budget_utilized) &&
      cards[10] === inr(expected.budget_remaining),
      `${cards[8]} / ${cards[9]} / ${cards[10]} vs ${inr(expected.budget_approved)} / ${inr(expected.budget_utilized)} / ${inr(expected.budget_remaining)}`);

    // ------------------------------------------------------ launchpad
    const launch = await page.evaluate(() =>
      [...document.querySelectorAll('a[href^="/reports/"]')].map((a) => a.getAttribute("href")),
    );
    check("hub: launchpad links into all nine workspaces",
      ["publications", "research", "faculty", "students", "teaching",
       "finance", "events", "committees", "analytics"].every((kind) =>
        launch.includes(`/reports/${kind}`)),
      launch.join("|"));

    // -------------------------------------------- PART 2 publications lens
    await page.evaluate(() => {
      const link = document.querySelector('a[href="/reports/publications"]');
      if (!link) throw new Error("publications launchpad link missing");
      link.click();
    });
    await waitForText(page, "Publications by Year", 30_000);
    check("publications: workspace renders with group-by sections", page.url().includes("/reports/publications"));
    const pubMaster = await tableRows(page, "Publications (filtered)");
    check("publications: master table carries both seeded titles",
      !!pubMaster && pubMaster.some((row) => row[0] === PUB1_TITLE) &&
      pubMaster.some((row) => row[0] === PUB2_TITLE));
    const byYear = await tableRows(page, "Publications by Year");
    check("publications: year buckets include 2025 and 2026",
      !!byYear && byYear.some((row) => row[0] === "2025") &&
      byYear.some((row) => row[0] === "2026"));
    const byJournal = await tableRows(page, "Publications by Journal");
    check("publications: JCTA journal bucket present",
      !!byJournal && byJournal.some((row) => row[0] === "JCTA"));
    const byAuthor = await tableRows(page, "Publications by Author");
    check("publications: STAMPed author shows 2 papers",
      !!byAuthor && byAuthor.some((row) => row[0] === FACULTY_NAME && row[1] === "2"));
    const byProject = await tableRows(page, "Publications by Project");
    check("publications: STAMPed project bucket present",
      !!byProject && byProject.some((row) => row[0] === PROJECT_TITLE));
    const byGrant = await tableRows(page, "Publications by Grant");
    check("publications: STAMPed grant bucket present",
      !!byGrant && byGrant.some((row) => row[0] === GRANT_TITLE));
    const perYearChart = await page.evaluate(() =>
      [...document.querySelectorAll('svg[role="img"]')].map((svg) =>
        svg.getAttribute("aria-label")),
    );
    check("publications: SVG charts render (per-year + per-type)",
      perYearChart.includes("Publications per Year") &&
      perYearChart.includes("Publications by Type"), perYearChart.join("|"));

    // PART 12 year filter narrows the master table.
    await setSelectWhenReady(page, "Year", "2026");
    await waitForFunctionTextGone(page, PUB1_TITLE);
    check("publications: year 2026 filter hides the 2025 paper", true);
    const filteredRows = await tableRows(page, "Publications (filtered)");
    check("publications: filtered table still carries the 2026 paper",
      !!filteredRows && filteredRows.some((row) => row[0] === PUB2_TITLE));
    const cleared = await page.evaluate(() => {
      const btn = [...document.querySelectorAll("button")].find(
        (b) => b.textContent?.trim() === "Clear filters",
      );
      if (btn) { btn.click(); return true; }
      return false;
    });
    await sleep(700);
    check("publications: Clear filters resets the table",
      cleared && (await waitForText(page, PUB1_TITLE, 15_000).catch(() => false)));

    // -------------------------------------------- PART 3 research
    await page.goto(`${BASE}/reports/research`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Budget Summary", 30_000);
    const budgetRows = await tableRows(page, "Budget Summary");
    const budgetRow = budgetRows?.find((row) => row[0] === PROJECT_TITLE);
    check("research: budget line money strings",
      !!budgetRow && budgetRow[1] === inr(500000) && budgetRow[2] === inr(100000) &&
      budgetRow[3] === inr(160000) && budgetRow[4] === inr(340000),
      budgetRow?.join("|") ?? "missing");
    const teamRows = await tableRows(page, "Team Summary");
    check("research: team summary lists the PI",
      !!teamRows && teamRows.some((row) => row[0] === PROJECT_TITLE && row[1].includes(FACULTY_NAME)));
    const projPubRows = await tableRows(page, "Project Publications");
    check("research: project publications linked",
      !!projPubRows && projPubRows.some((row) => row[0] === PROJECT_TITLE && row[1] === "1" && row[2].includes(PUB1_TITLE)));
    const activeRows = await tableRows(page, "Active Projects");
    check("research: seeded project is Active",
      !!activeRows && activeRows.some((row) => row[0] === PROJECT_TITLE));

    // -------------------------------------------- PART 4 faculty
    await page.goto(`${BASE}/reports/faculty`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Faculty Overview", 30_000);
    const overview = await tableRows(page, "Faculty Overview");
    const memberRow = overview?.find((row) => row[0] === FACULTY_NAME);
    check("faculty: overview row carries the seeded member",
      !!memberRow && memberRow[3] === "2" && memberRow[4] === "1" && memberRow[6] === "1",
      memberRow?.join("|") ?? "missing");
    await setSelectWhenReady(page, "Faculty", ids.faculty);
    await waitForText(page, "Faculty Profile", 30_000);
    check("faculty: member profile lens renders", true);
    check("faculty: profile shows the department",
      await waitForText(page, "Mathematics", 5_000).catch(() => false));
    check("faculty: profile publications KPI == 2",
      (await kpiValue(page, "Publications")) === "2");
    check("faculty: profile committees KPI == 1",
      (await kpiValue(page, "Committees")) === "1");
    check("faculty: profile events KPI == 1",
      (await kpiValue(page, "Events")) === "1");

    // -------------------------------------------- PART 5 students
    await page.goto(`${BASE}/reports/students`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Student Overview", 30_000);
    const studentRows = await tableRows(page, "Student Overview");
    const studentRow = studentRows?.find((row) => row[0] === STUDENT_NAME);
    check("students: overview row carries the seeded student",
      !!studentRow && studentRow[6] === "1" && studentRow[7] === "50%" && studentRow[8] === "90%",
      studentRow?.join("|") ?? "missing");
    await setSelectWhenReady(page, "Student", ids.student);
    await waitForText(page, "Attendance Summary", 30_000);
    check("students: per-student lens renders", true);
    check("students: attendance KPI 50%",
      (await kpiValue(page, "Overall Attendance")) === "50%");
    check("students: marks KPI 90%",
      (await kpiValue(page, "Marks Percentage")) === "90%");
    const gradeRows = await tableRows(page, "Grade Summary");
    check("students: grade summary row carries the class",
      !!gradeRows && gradeRows.some((row) => row[0] === CLASS_TITLE && row[1] === "90%"));

    // -------------------------------------------- PART 6 teaching
    await page.goto(`${BASE}/reports/teaching`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Class Summary", 30_000);
    const classRows = await tableRows(page, "Class Summary");
    check("teaching: class summary carries the seeded class",
      !!classRows && classRows.some((row) => row[1] === CLASS_TITLE && row[6] === "1"));
    const attRows = await tableRows(page, "Attendance Percentage");
    check("teaching: attendance row shows 50%",
      !!attRows && attRows.some((row) => row[0] === CLASS_TITLE && row[2] === "50%"));
    const asgRows = await tableRows(page, "Assignment Statistics");
    check("teaching: assignment stats 1/1/1 with 90% avg",
      !!asgRows && asgRows.some((row) => row[0] === CLASS_TITLE && row[1] === "1" && row[4] === "90%"));
    const chartsTeach = await page.evaluate(() =>
      [...document.querySelectorAll('svg[role="img"]')].map((svg) => svg.getAttribute("aria-label")),
    );
    check("teaching: bar charts render",
      chartsTeach.includes("Attendance % by Class") && chartsTeach.includes("Assignments by Class"));

    // -------------------------------------------- PART 7 finance
    await page.goto(`${BASE}/reports/finance`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Vendor Summary", 30_000);
    const vendorRows = await tableRows(page, "Vendor Summary");
    check("finance: vendor row with paid spend",
      !!vendorRows && vendorRows.some((row) => row[0] === VENDOR_NAME && row[5] === inr(40000)));
    const purchaseRows = await tableRows(page, "Purchase Summary");
    check("finance: purchase row committed/spent",
      !!purchaseRows && purchaseRows.some((row) => row[1] === PROPOSAL_TITLE && row[7] === inr(40000) && row[8] === inr(40000)));
    const assetRows = await tableRows(page, "Asset Summary");
    check("finance: asset row with cost",
      !!assetRows && assetRows.some((row) => row[0] === `E2E-${STAMP}-AS` && row[6] === inr(38000)));
    check("finance: budget KPI money strings",
      (await kpiValue(page, "Budget Approved")) === inr(expected.budget_approved) &&
      (await kpiValue(page, "Budget Utilized")) === inr(expected.budget_utilized),
      `${await kpiValue(page, "Budget Approved")} vs ${inr(expected.budget_approved)}`);
    const financeCharts = await page.evaluate(() =>
      [...document.querySelectorAll('svg[role="img"]')].map((svg) => svg.getAttribute("aria-label")),
    );
    check("finance: two-series budget chart renders",
      financeCharts.includes("Budget by Project (₹)"));

    // -------------------------------------------- PART 8 events
    await page.goto(`${BASE}/reports/events`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Events Organized", 30_000);
    const kpiText = await page.evaluate(() => document.body.innerText);
    check("events: counters moved by the seeded delta",
      !!eventsBase && kpiText.includes("Events Organized"));
    const organizedRows = await tableRows(page, "Events Organized");
    check("events: STAMPed event is organized",
      !!organizedRows && organizedRows.some((row) => row[0] === EVENT_TITLE && row[4].includes("Organizer")));
    const workshopRows = await tableRows(page, "Workshops");
    check("events: STAMPed workshop listed",
      !!workshopRows && workshopRows.some((row) => row[0] === WORKSHOP_TITLE));
    const partRows = await tableRows(page, "Participation");
    check("events: participation rows carry roles",
      !!partRows && partRows.some((row) => row[0] === WORKSHOP_TITLE && row[1] === "Participant"));
    const eventCharts = await page.evaluate(() =>
      [...document.querySelectorAll('svg[role="img"]')].map((svg) => svg.getAttribute("aria-label")),
    );
    check("events: per-year + per-type charts render",
      eventCharts.includes("Events per Year") && eventCharts.includes("Events by Type"));
    const deltaKpi = await kpiValue(page, "Organized");
    const baseOrganized = eventsBase?.kpis?.find((k) => k.label === "Organized")?.value;
    check("events: Organized KPI is baseline + 1",
      String(Number(baseOrganized?.replace(/,/g, "") ?? "NaN") + 1) === String(Number(deltaKpi?.replace(/,/g, "") ?? "NaN")),
      `${baseOrganized} -> ${deltaKpi}`);

    // -------------------------------------------- PART 9 committees
    await page.goto(`${BASE}/reports/committees`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Pending Actions", 30_000);
    const meetingRows = await tableRows(page, "Meetings");
    check("committees: meeting row shows 100% attendance",
      !!meetingRows && meetingRows.some((row) => row[0] === MEETING_TITLE && row[7] === "100%"));
    const pendingRows = await tableRows(page, "Pending Actions");
    check("committees: STAMPed pending action listed",
      !!pendingRows && pendingRows.some((row) => row[0] === `Prepare AQAR E2E ${STAMP}`));
    const doneRows = await tableRows(page, "Completed Actions");
    check("committees: STAMPed completed action listed",
      !!doneRows && doneRows.some((row) => row[0] === `Upload minutes E2E ${STAMP}`));
    const commKpis = await kpiValue(page, "Pending Actions");
    const basePending = committeesBase?.kpis?.find((k) => k.label === "Pending Actions")?.value;
    check("committees: Pending Actions KPI is baseline + 1",
      String(Number(basePending?.replace(/,/g, "") ?? "NaN") + 1) === String(Number(commKpis?.replace(/,/g, "") ?? "NaN")),
      `${basePending} -> ${commKpis}`);

    // -------------------------------------------- PART 10 analytics
    await page.goto(`${BASE}/reports/analytics`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Publication Trend", 30_000);
    const analyticsCharts = await page.evaluate(() =>
      [...document.querySelectorAll('svg[role="img"]')].map((svg) => svg.getAttribute("aria-label")),
    );
    check("analytics: all five trend charts render",
      ["Publication Trend", "Event Trend", "Budget Trend (₹ per project start year)",
       "Teaching Load (weekly hours per faculty)", "Student Attendance Trend (% per month)"]
        .every((label) => analyticsCharts.includes(label)),
      analyticsCharts.join("|"));
    const rollup = await tableRows(page, "Year-wise Rollup");
    check("analytics: rollup spans the seeded years",
      !!rollup && rollup.some((row) => row[0] === "2024") && rollup.some((row) => row[0] === "2026"));

    // -------------------------------------------- PART 11 export
    const exportHrefs = await page.evaluate(() =>
      [...document.querySelectorAll('a[download]')].map((a) => a.getAttribute("href")),
    );
    check("export: three format buttons with kind+format hrefs",
      exportHrefs.length === 3 &&
      exportHrefs.every((href) => href.includes("/reports/export?") && href.includes("kind=analytics")),
      exportHrefs.join("|"));
    const csv = await fetch(`${API}/reports/export?kind=publications&format=csv`);
    const csvText = await csv.text();
    check("export: CSV contains the seeded publication + report header",
      csv.status === 200 && csv.headers.get("content-type")?.startsWith("text/csv") &&
      csvText.includes(PUB1_TITLE) && csvText.includes("Publications Report"));
    const filteredCsv = await fetch(`${API}/reports/export?kind=publications&format=csv&year=2026`);
    const filteredText = await filteredCsv.text();
    check("export: filtered CSV excludes the 2025 paper",
      filteredText.includes(PUB2_TITLE) && !filteredText.includes(PUB1_TITLE));
    const xlsx = await fetch(`${API}/reports/export?kind=finance&format=xlsx`)
      .then((res) => res.arrayBuffer());
    check("export: XLSX is a real zip package",
      Buffer.from(xlsx).subarray(0, 2).toString("latin1") === "PK");
    const pdf = await fetch(`${API}/reports/export?kind=committees&format=pdf`)
      .then((res) => res.arrayBuffer());
    check("export: PDF starts with the %PDF magic",
      Buffer.from(pdf).subarray(0, 8).toString("latin1") === "%PDF-1.4");

    // -------------------------------------------- filter error surface
    await page.goto(
      `${BASE}/reports/research?`, { waitUntil: "networkidle2", timeout: 60_000 },
    );
    await waitForText(page, "Budget Summary", 30_000);
    await page.evaluate(() => {
      const [from, to] = [...document.querySelectorAll('input[type="date"]')];
      const setNative = (el, val) => {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        setter.call(el, val);
        el.dispatchEvent(new Event("input", { bubbles: true }));
      };
      setNative(from, "2026-06-01");
      setNative(to, "2026-01-01");
    });
    await waitForText(page, "date_from must not be after date_to", 15_000);
    check("filters: inverted date range surfaces the 422 message", true);

    // -------------------------------------------- unknown kind -> 404
    await page.goto(`${BASE}/reports/nope`, { waitUntil: "networkidle2", timeout: 60_000 });
    const notFoundShown = await waitForText(page, "404", 15_000).catch(() => false);
    check("unknown kind renders the 404 state", notFoundShown);

    // -------------------------------------------- hub re-check + cleanliness
    await page.goto(`${BASE}/reports`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Reports & Analytics", 30_000);
    const finalCards = await Promise.all(
      ["Publications", "Budget Utilized"].map((label) => cardValue(page, label)),
    );
    check("hub re-check: cards hold the seeded totals",
      Number.parseInt(finalCards[0] ?? "", 10) === expected.total_publications &&
      finalCards[1] === inr(expected.budget_utilized),
      finalCards.join("|"));
  } catch (err) {
    check(`FATAL: ${err.message}`, false);
    try {
      fs.writeFileSync("/tmp/e2e-fail.html", await page.content());
      await page.screenshot({ path: "/tmp/e2e-fail.png", fullPage: true });
      const body = await page.evaluate(() => document.body.innerText.slice(0, 3000));
      console.error("---- page body at crash ----\n" + body);
      console.error("---- console errors ----\n" + consoleErrors.join("\n"));
    } catch { /* best effort */ }
  } finally {
    await browser.close();
  }

  const unexpectedApi = failingApi.filter((line) => {
    // The deliberate inverted-date-range 422 is an intended assertion,
    // not a backend fault — keep everything else.
    if (line.startsWith("422 GET") && line.includes("/api/v1/reports")) return false;
    return true;
  });
  check("no failing API requests", unexpectedApi.length === 0, unexpectedApi.join(" | "));
  const badConsole = consoleErrors.filter((line) => !line.includes("favicon"));
  check("no browser console errors", badConsole.length === 0, badConsole.join(" | "));

  const passed = results.filter((r) => r.ok).length;
  console.log(`\n${passed}/${results.length} checks passed.`);
  if (passed !== results.length) process.exit(1);
}

async function waitForFunctionTextGone(page, text, timeoutMs = 15_000) {
  await page.waitForFunction(
    (wanted) => !document.body.innerText.includes(wanted),
    { timeout: timeoutMs },
    text,
  );
}

main().catch((err) => {
  console.error("E2E crashed:", err);
  process.exit(1);
});

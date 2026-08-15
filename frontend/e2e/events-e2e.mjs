/**
 * Events & Academic Activities module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   events hub (PART 9 cards with exact baseline+delta values) -> PART 1
 *   directory -> PART 10 search + type/year/role/department/organizer/status
 *   filters -> create via the modal (people/research links + registration
 *   counters) -> duplicate event-code 409 in the modal -> the workspace
 *   (record + registration, PART 2 participation with a certificate, PART 3
 *   speakers, PART 4 schedule with the speaker picker, PART 8 linked
 *   publications with relations, linked faculty/students panels, certificates
 *   lens, documents lens) -> dashboard re-check with exact deltas -> frozen
 *   publications page spot check -> delete flow -> 404 state.
 *
 * The cross-module graph (faculty pair, student, publication, project,
 * grant, committee, certificate document) is seeded through the FROZEN
 * modules' own APIs. Dashboard assertions are BASELINE + DELTA so the suite
 * composes with the other E2E suites in a shared database.
 *
 * Usage:
 *   node tests/events-e2e.mjs         # http://localhost:3000
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
const FACULTY_A_NAME = `Dr. Meera Krishnan E2E ${STAMP}`;
const FACULTY_B_NAME = `Prof. Arvind Rao E2E ${STAMP}`;
const STUDENT_NAME = `Asha Verma E2E ${STAMP}`;
const PUB_TITLE = `Ramsey Bounds E2E ${STAMP}`;
const PROJECT_TITLE = `Graph Theory E2E ${STAMP}`;
const GRANT_TITLE = `SERB Travel E2E ${STAMP}`;
const COMMITTEE_NAME = `IQAC Events E2E ${STAMP}`;
const DOC_TITLE = `Certificate E2E ${STAMP}.pdf`;

const EVENT_A_TITLE = `Mathematics Day E2E ${STAMP}`;
const EVENT_A_CODE = `EVT-${STAMP}-A`;
const EVENT_B_TITLE = `Invited Talk on Graph Ramsey E2E ${STAMP}`;
const EVENT_B_CODE = `EVT-${STAMP}-B`;
const EVENT_C_TITLE = `Cloud DevOps Workshop E2E ${STAMP}`;
const EVENT_C_CODE = `EVT-${STAMP}-C`;
const EVENT_C_ORGANIZER = `CSI Student Chapter ${STAMP}`;
const EVENT_D_TITLE = `Algebra Seminar E2E ${STAMP}`;
const EVENT_D_CODE = `EVT-${STAMP}-D`;
const TRASH_TITLE = `E2E Trash Event ${STAMP}`;
const TRASH_CODE = `EVT-${STAMP}-T`;

const SPEAKER_NAME = `Prof. E2E Raman ${STAMP}`;
const SESSION_TITLE = `Keynote E2E ${STAMP}`;

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

/** Read the big value of a PART 9 dashboard card by its label. */
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
  // The dashboard cards aggregate event objects only — capture the baseline
  // first so the assertions stay exact even in a database shared with other
  // E2E suites.
  const base = await getJson("/events/dashboard").then((r) => r.body);
  check(
    "seed: baseline dashboard captured",
    typeof base?.upcoming_events === "number",
    JSON.stringify(base),
  );

  const facultyA = await postJson("/faculty", {
    name: FACULTY_A_NAME,
    employee_id: `E2E-${STAMP}-FA1`,
    uploaded_by: "registrar:e2e",
    designation: "Professor",
    department: "Mathematics",
  }).then((r) => r.body);
  const facultyB = await postJson("/faculty", {
    name: FACULTY_B_NAME,
    employee_id: `E2E-${STAMP}-FA2`,
    uploaded_by: "registrar:e2e",
    designation: "Associate Professor",
    department: "Mathematics",
  }).then((r) => r.body);
  check("seed: two faculty created (linked people panels)",
    Boolean(facultyA.id && facultyB.id));

  const student = await postJson("/students", {
    name: STUDENT_NAME,
    student_type: "pg",
    roll_number: `E2E-${STAMP}-ST1`,
    uploaded_by: "registrar:e2e",
  }).then((r) => r.body);
  const publication = await postJson("/publications", {
    title: PUB_TITLE,
    publication_type: "conference_paper",
    uploaded_by: "registrar:e2e",
    authors: [{ name: "M. Krishnan" }],
  }).then((r) => r.body);
  check("seed: student + publication created (link + presentation targets)",
    Boolean(student.id && publication.id));

  const project = await postJson("/research/projects", {
    title: PROJECT_TITLE,
    uploaded_by: "registrar:e2e",
    lifecycle_status: "active",
    budget_approved: 250000,
  }).then((r) => r.body);
  const grant = await postJson("/research/grants", {
    title: GRANT_TITLE,
    grant_number: `E2E-${STAMP}-GT1`,
    uploaded_by: "registrar:e2e",
    amount: 50000,
    links: { projects: [project.id], funding_agencies: [] },
  }).then((r) => r.body);
  const committee = await postJson("/committees", {
    name: COMMITTEE_NAME,
    committee_code: `E2E-${STAMP}-IQ1`,
    committee_type: "cultural",
    department: "Administration",
    uploaded_by: "registrar:e2e",
    status: "active",
  }).then((r) => r.body);
  check("seed: project + grant + committee created (research/governance links)",
    Boolean(project.id && grant.id && committee.id));

  // EVENT A — the workspace hero (everything else is wired through the UI).
  const eventARes = await postJson("/events", {
    title: EVENT_A_TITLE,
    uploaded_by: "events:e2e",
    status: "active",
    event_code: EVENT_A_CODE,
    event_type: "mathematics_day",
    organizer: "Dept. of Mathematics",
    co_organizer: "Mathematics Club",
    venue: "Auditorium A",
    mode: "offline",
    start_date: "2026-12-22",
    end_date: "2026-12-23",
    department: "Mathematics",
    school: "School of Sciences",
    description: "Ramanujan birth anniversary celebrations.",
    objectives: "Popularise mathematics.",
    event_status: "planned",
    priority: "high",
    tags: ["annual"],
    participation: [{ role: "organizer", contribution: "Convened the team" }],
    registration: { expected_participants: 200, registered: 150 },
    links: {
      faculty: [facultyA.id],
      students: [],
      projects: [project.id],
      grants: [grant.id],
      committees: [committee.id],
    },
  });
  const eventA = eventARes.body;
  check(
    "seed: event A created (record + participation + registration + links)",
    eventARes.status === 201 &&
      eventA.event_code === EVENT_A_CODE &&
      eventA.event_status === "planned" &&
      eventA.registration?.expected_participants === 200 &&
      eventA.links?.faculty?.[0]?.id === facultyA.id,
    eventA.id ?? JSON.stringify(eventARes.body),
  );

  // EVENT B — completed invited talk with a speaking role.
  const eventBRes = await postJson("/events", {
    title: EVENT_B_TITLE,
    uploaded_by: "events:e2e",
    event_code: EVENT_B_CODE,
    event_type: "invited_talk",
    organizer: "Dept. of Mathematics",
    venue: "Seminar Hall 2",
    mode: "hybrid",
    start_date: "2026-05-15",
    department: "Mathematics",
    event_status: "completed",
    participation: [{ role: "speaker", contribution: "Delivered the talk" }],
  });
  check("seed: event B (completed invited talk, speaker role)",
    eventBRes.status === 201, String(eventBRes.status));
  const eventB = eventBRes.body;

  // EVENT C — attended workshop (year/organizer/type/department filter foil).
  const eventCRes = await postJson("/events", {
    title: EVENT_C_TITLE,
    uploaded_by: "events:e2e",
    event_code: EVENT_C_CODE,
    event_type: "workshop",
    organizer: EVENT_C_ORGANIZER,
    venue: "Computing Lab 4",
    mode: "offline",
    start_date: "2025-11-05",
    end_date: "2025-11-06",
    department: "Computer Science",
    event_status: "planned",
    participation: [{ role: "attendee" }],
  });
  check("seed: event C (attended workshop, 2025, distinct organizer)",
    eventCRes.status === 201, String(eventCRes.status));

  // TRASH event — the delete-flow target.
  const trash = await postJson("/events", {
    title: TRASH_TITLE,
    uploaded_by: "events:e2e",
    event_code: TRASH_CODE,
    event_type: "seminar",
    start_date: "2026-08-20",
    event_status: "planned",
  }).then((r) => r.body);
  check("seed: trash event (delete flow)", Boolean(trash.id));

  // API-side guard rails (seeded here; the browser gate allow-lists the 4xx).
  const dupCode = await postJson("/events", {
    title: `Duplicate Code ${STAMP}`,
    uploaded_by: "events:e2e",
    event_code: EVENT_A_CODE,
  });
  check("seed: duplicate event code rejected (409)", dupCode.status === 409);
  const dupTriple = await postJson("/events", {
    title: EVENT_A_TITLE,
    uploaded_by: "events:e2e",
    department: "Mathematics",
    start_date: "2026-12-22",
  });
  check("seed: duplicate title+department+date triple rejected (409)",
    dupTriple.status === 409);
  const badRole = await postJson("/events", {
    title: `Bad Role ${STAMP}`,
    uploaded_by: "events:e2e",
    participation: [{ role: "boss" }],
  });
  check("seed: unknown participation role rejected (422)", badRole.status === 422);
  const badPresentation = await postJson("/events", {
    title: `Bad Presentation ${STAMP}`,
    uploaded_by: "events:e2e",
    presentations: [{ publication_id: facultyA.id }],
  });
  check("seed: non-publication presentation rejected (422)",
    badPresentation.status === 422);
  const badTime = await postJson("/events", {
    title: `Bad Time ${STAMP}`,
    uploaded_by: "events:e2e",
    schedule: [{ title: "S", start_time: "25:00" }],
  });
  check("seed: malformed session time rejected (422)", badTime.status === 422);

  // PART 6: a certificate document attached to event A (frozen API).
  const form = new FormData();
  form.append("title", DOC_TITLE);
  form.append("document_type", "pdf");
  form.append("uploaded_by", "events:e2e");
  form.append("object_id", eventA.id);
  form.append("file", new Blob([`certificate ${STAMP}`], { type: "text/plain" }), "certificate.txt");
  const document_ = await fetch(`${API}/documents`, { method: "POST", body: form }).then((r) =>
    r.json(),
  );
  check("seed: certificate document attached to event A", Boolean(document_.id));

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

  const eventAPath = `/events/${encodeURIComponent(eventA.id)}`;

  try {
    // ------------------------------------------------------------- the hub
    await page.goto(`${BASE}/events`, { waitUntil: "networkidle0" });
    await page.waitForSelector("h1", { timeout: 30_000 });
    const heading = await page.$eval("h1", (el) => el.textContent?.trim());
    check("events hub loads", heading?.includes("Events") ?? false, heading ?? "");
    const navText = await page.$eval("nav", (nav) => nav.innerText);
    check("sidebar exposes the Events entry", navText.includes("Events"));

    const hub = await waitForText(page, "INVITED TALKS", 60_000);
    check(
      "PART 9 dashboard cards render (all seven labels)",
      /UPCOMING EVENTS[\s\S]*COMPLETED EVENTS[\s\S]*EVENTS ORGANIZED[\s\S]*EVENTS ATTENDED[\s\S]*CERTIFICATES[\s\S]*PRESENTATIONS[\s\S]*INVITED TALKS/.test(
        hub.toUpperCase(),
      ),
    );
    const firstCards = {
      upcoming: await cardValue(page, "UPCOMING EVENTS"),
      completed: await cardValue(page, "COMPLETED EVENTS"),
      organized: await cardValue(page, "EVENTS ORGANIZED"),
      attended: await cardValue(page, "EVENTS ATTENDED"),
      certificates: await cardValue(page, "CERTIFICATES"),
      presentations: await cardValue(page, "PRESENTATIONS"),
      invited: await cardValue(page, "INVITED TALKS"),
    };
    check(
      "PART 9 card values = baseline + seeded events (before UI wiring)",
      firstCards.upcoming === String(base.upcoming_events + 3) &&
        firstCards.completed === String(base.completed_events + 1) &&
        firstCards.organized === String(base.events_organized + 1) &&
        firstCards.attended === String(base.events_attended + 1) &&
        firstCards.certificates === String(base.certificates) &&
        firstCards.presentations === String(base.presentations) &&
        firstCards.invited === String(base.invited_talks + 1),
      JSON.stringify(firstCards),
    );

    // PART 1 directory: STAMP-scoped search sees exactly the four seeds.
    await setFieldValue(page, 'input[type="search"]', `E2E ${STAMP}`);
    const directory = await waitForText(page, "4 matches", 15_000);
    check(
      "PART 1 directory lists the seeded events (search-scoped)",
      directory.includes(EVENT_A_TITLE) &&
        directory.includes(EVENT_B_TITLE) &&
        directory.includes(EVENT_C_TITLE) &&
        directory.includes(TRASH_TITLE),
    );
    const rowA = await page.evaluate((title) => {
      const row = [...document.querySelectorAll("tr")].find((tr) =>
        tr.textContent?.includes(title),
      );
      return row?.textContent ?? "";
    }, EVENT_A_TITLE);
    check(
      "PART 1 row shows type/dates/venue/department/status badges",
      rowA.includes("Mathematics Day") &&
        rowA.includes("22 Dec 2026") &&
        rowA.includes("Auditorium A") &&
        rowA.includes("Mathematics") &&
        rowA.toUpperCase().includes("PLANNED") &&
        rowA.toUpperCase().includes("HIGH"),
      rowA.slice(0, 120),
    );

    // PART 10 filters — each narrows to the foil event(s).
    await setFieldValue(page, 'input[type="search"]', "");
    await sleep(700);
    await page.select('select[aria-label="Filter by event type"]', "workshop");
    await sleep(700);
    let filtered = await page.evaluate(() => document.body.innerText);
    check("PART 10 type filter -> only the workshop",
      filtered.includes(EVENT_C_TITLE) && !filtered.includes(EVENT_A_TITLE));
    await page.select('select[aria-label="Filter by event type"]', "all");

    await page.select('select[aria-label="Filter by year"]', "2025");
    await sleep(700);
    filtered = await page.evaluate(() => document.body.innerText);
    check("PART 10 year filter -> only the 2025 event",
      filtered.includes(EVENT_C_TITLE) && !filtered.includes(EVENT_A_TITLE));
    await page.select('select[aria-label="Filter by year"]', "");

    await page.select('select[aria-label="Filter by role"]', "speaker");
    await sleep(700);
    filtered = await page.evaluate(() => document.body.innerText);
    check("PART 10 role filter -> only the invited talk I spoke at",
      filtered.includes(EVENT_B_TITLE) && !filtered.includes(EVENT_A_TITLE));
    await page.select('select[aria-label="Filter by role"]', "all");

    await setFieldValue(page, 'input[aria-label="Filter by department"]', "computer");
    await sleep(900);
    filtered = await page.evaluate(() => document.body.innerText);
    check("PART 10 department filter -> only Computer Science",
      filtered.includes(EVENT_C_TITLE) && !filtered.includes(EVENT_B_TITLE));
    await setFieldValue(page, 'input[aria-label="Filter by department"]', "");

    await setFieldValue(page, 'input[aria-label="Filter by organizer"]', "csi");
    await sleep(900);
    filtered = await page.evaluate(() => document.body.innerText);
    check("PART 10 organizer filter -> only the CSI Chapter event",
      filtered.includes(EVENT_C_TITLE) && !filtered.includes(EVENT_A_TITLE));
    await setFieldValue(page, 'input[aria-label="Filter by organizer"]', "");

    await page.select('select[aria-label="Filter by status"]', "completed");
    await sleep(700);
    filtered = await page.evaluate(() => document.body.innerText);
    check("PART 10 status filter -> only the completed event",
      filtered.includes(EVENT_B_TITLE) && !filtered.includes(EVENT_A_TITLE));
    await page.select('select[aria-label="Filter by status"]', "all");
    await sleep(700);

    // ------------------------------------------------ create via the modal
    await clickButtonWithText(page, "New Event");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Event title", EVENT_D_TITLE);
    await typeInField(page, "Event code", EVENT_D_CODE);
    await page.select('select[aria-label="Event type"]', "seminar");
    await page.select('select[aria-label="Event status"]', "planned");
    await typeInField(page, "Organizer", "Dept. of Mathematics");
    await typeInField(page, "Venue", "Room 12");
    await page.select('select[aria-label="Mode"]', "offline");
    await typeInField(page, "Start date", "2026-03-10");
    await typeInField(page, "End date", "2026-03-10");
    await typeInField(page, "Department", "Mathematics");
    await typeInField(page, "School", "School of Sciences");
    await page.select('select[aria-label="Priority"]', "medium");
    await typeInField(page, "Tags", "e2e, seminar");
    await typeInField(page, "Description", "Modal seminar description");
    await typeInField(page, "Objectives", "Modal objectives");
    await typeInField(page, "Outcome", "Modal outcome");
    await typeInField(page, "Expected", "100");
    await typeInField(page, "Registered", "80");
    await typeInField(page, "Present", "0");
    await typeInField(page, "Certificates issued", "0");
    await waitForOption(page, 'select[aria-label="Linked faculty"]', facultyA.id);
    await page.select('select[aria-label="Linked faculty"]', facultyA.id);
    await waitForOption(page, 'select[aria-label="Linked students"]', student.id);
    await page.select('select[aria-label="Linked students"]', student.id);
    await waitForOption(page, 'select[aria-label="Linked projects"]', project.id);
    await page.select('select[aria-label="Linked projects"]', project.id);
    await clickButtonWithText(page, "Create event");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "created successfully", 15_000);
    check("create: event registered via the modal (links + registration counters)", true);
    const modalEvent = await waitApi(
      `/events?q=${encodeURIComponent(`seminar ${STAMP}`)}`,
      (body) =>
        body.items?.length >= 1 &&
        body.items[0].registration?.expected_participants === 100 &&
        body.items[0].links?.students?.[0]?.id === student.id &&
        body.items[0].links?.projects?.[0]?.id === project.id,
    );
    check("create: modal event carries counters + resolved links",
      Boolean(modalEvent.items?.[0]?.id));

    // duplicate code -> backend 409 surfaces in the modal
    await clickButtonWithText(page, "New Event");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Event title", `Duplicate ${STAMP}`);
    await typeInField(page, "Event code", EVENT_D_CODE);
    await clickButtonWithText(page, "Create event");
    await page.waitForSelector('form[role="dialog"] [role="alert"]', { timeout: 15_000 });
    const dupeAlert = await page.$eval(
      'form[role="dialog"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check(
      "duplicate event code surfaces the backend 409 in the modal",
      dupeAlert.toLowerCase().includes("duplicate") ||
        dupeAlert.toLowerCase().includes("already carries"),
      dupeAlert.slice(0, 90),
    );
    await clickButtonWithText(page, "Cancel", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 10_000,
    });

    // --------------------------------------------------------- the workspace
    await setFieldValue(page, 'input[type="search"]', `mathematics day ${STAMP}`);
    await waitForText(page, EVENT_A_TITLE, 15_000);
    await clickLinkWithText(page, EVENT_A_TITLE);
    await page.waitForSelector("h1", { timeout: 30_000 });
    const workspace = await waitForText(page, "Event Record", 30_000);
    check(
      "workspace loads with the PART 1 record",
      workspace.includes(EVENT_A_CODE) &&
        workspace.includes("Ramanujan birth anniversary") &&
        workspace.includes("Mathematics Club") &&
        workspace.includes("School of Sciences"),
    );
    check(
      "workspace shows the PART 5 registration counters + organizer role",
      workspace.includes("Expected participants") &&
        workspace.includes("200") &&
        workspace.includes("150") &&
        workspace.toUpperCase().includes("ORGANIZER"),
    );

    // PART 2 participation: add a coordinator row carrying the certificate.
    await page.click('button[aria-label="Edit my participation"]');
    await waitForText(page, "My Participation (1)", 10_000);
    await clickButtonWithText(page, "Add participation");
    await page.select('select[aria-label="Participation 2 role"]', "coordinator");
    await setFieldValue(
      page, 'input[aria-label="Participation 2 contribution"]', "Stage management",
    );
    await waitForOption(page, 'select[aria-label="Participation 2 certificate"]', document_.id);
    await page.select('select[aria-label="Participation 2 certificate"]', document_.id);
    await setFieldValue(
      page, 'input[aria-label="Participation 2 remarks"]', "Collected at valedictory",
    );
    await clickButtonWithText(page, "Save");
    await waitApi(eventAPath, (body) =>
      Boolean(
        body.participation?.length === 2 &&
          body.participation[1].role === "coordinator" &&
          body.participation[1].certificate?.id === document_.id,
      ),
    );
    const participationNow = await waitForText(page, "My Participation (2)", 15_000);
    check(
      "PART 2: coordinator row saved with the resolved certificate",
      participationNow.includes(DOC_TITLE) && participationNow.includes("Stage management"),
    );

    // PART 3 speakers: add the keynote speaker.
    await page.click('button[aria-label="Edit speakers"]');
    await clickButtonWithText(page, "Add speaker");
    await setFieldValue(page, 'input[aria-label="Speaker 1 name"]', SPEAKER_NAME);
    await setFieldValue(page, 'input[aria-label="Speaker 1 affiliation"]', "IIT Delhi E2E");
    await setFieldValue(page, 'input[aria-label="Speaker 1 designation"]', "Professor");
    await setFieldValue(page, 'input[aria-label="Speaker 1 email"]', "raman@iitd-e2e.example");
    await setFieldValue(page, 'input[aria-label="Speaker 1 phone"]', "9810012345");
    await setFieldValue(
      page, 'input[aria-label="Speaker 1 biography"]', "Combinatorial number theory.",
    );
    await waitForOption(page, 'select[aria-label="Speaker 1 photo"]', document_.id);
    await page.select('select[aria-label="Speaker 1 photo"]', document_.id);
    await clickButtonWithText(page, "Save");
    const withSpeaker = await waitApi(eventAPath, (body) =>
      Boolean(
        body.speakers?.length === 1 &&
          body.speakers[0].row_id &&
          body.speakers[0].photo?.id === document_.id,
      ),
    );
    const speakerRowId = withSpeaker.speakers[0].row_id;
    const speakersNow = await waitForText(page, "Speakers (1)", 15_000);
    check(
      "PART 3: speaker saved with row id + resolved photo",
      speakersNow.includes(SPEAKER_NAME) && speakersNow.includes("IIT Delhi E2E"),
      `row_id=${speakerRowId}`,
    );

    // PART 4 schedule: keynote session wired to the speaker row id.
    await page.click('button[aria-label="Edit schedule"]');
    await clickButtonWithText(page, "Add session");
    await setFieldValue(page, 'input[aria-label="Session 1 title"]', SESSION_TITLE);
    await setFieldValue(page, 'input[aria-label="Session 1 date"]', "2026-12-22");
    await setFieldValue(page, 'input[aria-label="Session 1 start time"]', "10:00");
    await setFieldValue(page, 'input[aria-label="Session 1 end time"]', "11:00");
    await waitForOption(page, 'select[aria-label="Session 1 speaker"]', speakerRowId);
    await page.select('select[aria-label="Session 1 speaker"]', speakerRowId);
    await setFieldValue(page, 'input[aria-label="Session 1 venue"]', "Auditorium A");
    await setFieldValue(page, 'input[aria-label="Session 1 chairperson"]', FACULTY_A_NAME);
    await clickButtonWithText(page, "Save");
    await waitApi(eventAPath, (body) =>
      Boolean(
        body.schedule?.length === 1 &&
          body.schedule[0].speaker_name === SPEAKER_NAME &&
          body.schedule[0].start_time === "10:00",
      ),
    );
    const scheduleNow = await waitForText(page, "Schedule (1)", 15_000);
    check(
      "PART 4: session saved; speaker name resolves from the speakers list",
      scheduleNow.includes(SESSION_TITLE) &&
        scheduleNow.includes("10:00 – 11:00") &&
        scheduleNow.includes(SPEAKER_NAME),
    );

    // PART 8 linked publications: presented paper with a relation badge.
    await page.click('button[aria-label="Edit linked publications"]');
    await clickButtonWithText(page, "Add publication");
    await waitForOption(page, 'select[aria-label="Presentation 1 publication"]', publication.id);
    await page.select('select[aria-label="Presentation 1 publication"]', publication.id);
    await page.select('select[aria-label="Presentation 1 relation"]', "presented_paper");
    await setFieldValue(
      page, 'input[aria-label="Presentation 1 remarks"]', "Best session talk",
    );
    await clickButtonWithText(page, "Save");
    await waitApi(eventAPath, (body) =>
      Boolean(
        body.presentations?.length === 1 &&
          body.presentations[0].publication_title === PUB_TITLE &&
          body.links?.publications?.[0]?.id === publication.id,
      ),
    );
    const presentationsNow = await waitForText(page, "Linked Publications (1)", 15_000);
    check(
      "PART 8: publication linked with the Presented Paper relation",
      presentationsNow.includes(PUB_TITLE) &&
        presentationsNow.toUpperCase().includes("PRESENTED PAPER"),
    );

    // Linked faculty: seeded link + add the second faculty (whole-links save).
    await page.click('button[aria-label="Edit linked faculty"]');
    await waitForOption(page, 'select[aria-label="Linked faculty"]', facultyB.id);
    await page.select('select[aria-label="Linked faculty"]', facultyA.id, facultyB.id);
    await clickButtonWithText(page, "Save");
    await waitApi(eventAPath, (body) => body.links?.faculty?.length === 2);
    const facultyNow = await waitForText(page, "Linked Faculty (2)", 15_000);
    check(
      "PART 7: linked faculty panel saves both picks",
      facultyNow.includes(FACULTY_A_NAME) && facultyNow.includes(FACULTY_B_NAME),
    );

    // Linked students: from empty to the seeded student.
    await page.click('button[aria-label="Edit linked students"]');
    await waitForOption(page, 'select[aria-label="Linked students"]', student.id);
    await page.select('select[aria-label="Linked students"]', student.id);
    await clickButtonWithText(page, "Save");
    await waitApi(eventAPath, (body) => body.links?.students?.length === 1);
    const studentsNow = await waitForText(page, "Linked Students (1)", 15_000);
    check("PART 7: linked students panel saves the student",
      studentsNow.includes(STUDENT_NAME));

    // Certificates + research/governance lens + documents lens.
    const certificatesNow = await waitForText(page, "Certificates (1)", 15_000);
    check(
      "certificates lens lists the coordinator certificate",
      certificatesNow.includes(DOC_TITLE) &&
        certificatesNow.toUpperCase().includes("COORDINATOR"),
    );
    const linksNow = await page.evaluate(() => document.body.innerText);
    check(
      "research/governance lens shows project + publication groups",
      linksNow.includes(PROJECT_TITLE) && linksNow.includes(PUB_TITLE),
    );
    check(
      "PART 6 documents lens lists the attached certificate",
      linksNow.includes(DOC_TITLE),
    );

    // Hub cards after the UI wiring (baseline + 4 upcoming incl. the modal D
    // and the trash seed; +1 certificate; +1 presentation).
    await page.goto(`${BASE}/events`, { waitUntil: "networkidle0" });
    await waitForText(page, "INVITED TALKS", 60_000);
    const finalCards = {
      upcoming: await cardValue(page, "UPCOMING EVENTS"),
      completed: await cardValue(page, "COMPLETED EVENTS"),
      organized: await cardValue(page, "EVENTS ORGANIZED"),
      attended: await cardValue(page, "EVENTS ATTENDED"),
      certificates: await cardValue(page, "CERTIFICATES"),
      presentations: await cardValue(page, "PRESENTATIONS"),
      invited: await cardValue(page, "INVITED TALKS"),
    };
    check(
      "PART 9 card values reflect the UI wiring (certificate + presentation)",
      finalCards.upcoming === String(base.upcoming_events + 4) &&
        finalCards.completed === String(base.completed_events + 1) &&
        finalCards.organized === String(base.events_organized + 1) &&
        finalCards.attended === String(base.events_attended + 1) &&
        finalCards.certificates === String(base.certificates + 1) &&
        finalCards.presentations === String(base.presentations + 1) &&
        finalCards.invited === String(base.invited_talks + 1),
      JSON.stringify(finalCards),
    );

    // ------------------------------------------------- frozen spot check
    await page.goto(`${BASE}/publications`, { waitUntil: "networkidle0" });
    await page.waitForSelector("h1", { timeout: 30_000 });
    await setFieldValue(page, 'input[type="search"]', PUB_TITLE);
    const pubDirectory = await waitForText(page, PUB_TITLE, 15_000);
    check("frozen publications module lists the seeded paper (unregressed)",
      pubDirectory.includes(PUB_TITLE));

    // --------------------------------------------------------- delete flow
    await page.goto(`${BASE}/events`, { waitUntil: "networkidle0" });
    await setFieldValue(page, 'input[type="search"]', TRASH_TITLE);
    await waitForText(page, TRASH_TITLE, 15_000);
    await clickLinkWithText(page, TRASH_TITLE);
    await waitForText(page, "Event Record", 30_000);
    await clickButtonWithText(page, "Delete");
    await page.waitForSelector('[role="alertdialog"], form[role="dialog"]', {
      timeout: 10_000,
    });
    await clickButtonWithText(page, "Delete", { inDialog: true });
    await waitForText(page, "was deleted", 15_000);
    const afterDelete = await waitApi(
      `/events?q=${encodeURIComponent(`trash ${STAMP}`)}`,
      (body) => body.total_count === 0,
      10_000,
    );
    check("delete: trash event removed (toast + API)", afterDelete.total_count === 0);

    // Dashboard settles back (trash event was one of the four upcoming).
    await page.goto(`${BASE}/events`, { waitUntil: "networkidle0" });
    await waitForText(page, "INVITED TALKS", 60_000);
    const settledCards = {
      upcoming: await cardValue(page, "UPCOMING EVENTS"),
      organized: await cardValue(page, "EVENTS ORGANIZED"),
    };
    check(
      "PART 9 upcoming card drops after the delete",
      settledCards.upcoming === String(base.upcoming_events + 3) &&
        settledCards.organized === String(base.events_organized + 1),
      JSON.stringify(settledCards),
    );

    // ------------------------------------------------------------- 404 state
    await page.goto(`${BASE}/events/${encodeURIComponent("obj:event:MISSING")}`, {
      waitUntil: "networkidle0",
    });
    const missing = await waitForText(page, "Event not found", 15_000);
    check("missing id renders the 404 state", missing.includes("Event not found"));

    // --------------------------------------------------------- cleanliness
    const hostileApi = failedResponses.filter((line) => {
      if (!line.includes("/api/v1/")) return false;
      // Intentional check above: duplicate event code (modal) is on purpose.
      if (line.startsWith("409 POST") && line.endsWith("/api/v1/events")) return false;
      // The 404-state check above opens a deliberately missing id.
      if (line.startsWith("404 GET") && line.includes("/api/v1/events/obj:event:MISSING")) {
        return false;
      }
      return true;
    });
    check("no failing API requests (>=400)", hostileApi.length === 0, hostileApi[0] ?? "");
    const hostile = consoleErrors.filter(
      (line) =>
        !line.includes("favicon") &&
        !line.includes("404 (Not Found)") && // /favicon.ico — no favicon ships yet
        // The intentional 409 check logs as a console error in chromium.
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

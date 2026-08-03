/**
 * Productivity Hub module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   sidebar entry -> PART 8 hub with five tabs
 *   -> Overview: PART 6 dashboard cards (exact baseline+delta) + PART 5
 *      reminder buckets (overdue / due today / upcoming today / tomorrow /
 *      this week)
 *   -> Calendar tab: PART 1 Day/Week/Month/Agenda views + PART 2 source
 *      toggle chips rendered from the SAME feed the API returns, plus
 *      personal calendar entries (create via calendar "Add entry", edit,
 *      delete)
 *   -> Tasks tab: PART 3 personal tasks — server-side filters, create via
 *      modal, edit due date, pin, complete, delete (all deltas verified)
 *   -> Overview re-check after the task stories (explicit recomputed counts)
 *   -> Notifications tab: PART 4 center — state tabs, unread counter chip,
 *      pin / read / archive / snooze(prompt) / unsnooze, manual note, PART 5
 *      engine refresh idempotency ("1 new" deterministically: the task whose
 *      due date the suite moved across buckets), delete from the archived
 *      shelf, API recount parity
 *   -> Search tab: PART 7 unified search over tasks + notifications +
 *      calendar (source scope filter, date window, priority filter,
 *      task/calendar dual-lens duplicates by design)
 *   -> cleanliness gates: zero failed API calls, zero console/page errors.
 *
 * The dated world (class + weekly lecture today + attendance session,
 * assignment due d+4, committee + meeting + overdue action, three events,
 * research project + pending milestone, grant + overdue installment, vendor +
 * proposal with open PO and unpaid bill, personal tasks / entries /
 * notifications) is seeded through the FROZEN modules' own APIs and the new
 * productivity API. Global counters are asserted as BASELINE + DELTA so the
 * suite composes with the other E2E suites in a shared database. Every date
 * is derived from TODAY so the suite passes on any day of the year.
 *
 * Usage:
 *   node tests/productivity-e2e.mjs         # http://localhost:3000
 */
import puppeteer from "puppeteer";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

const results = [];
const check = (name, ok, extra = "") => {
  results.push({ name, ok, extra });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? ` — ${extra}` : ""}`);
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ---------------------------------------------------------------- dates
const pad = (value) => String(value).padStart(2, "0");
const toIso = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
/** ISO date `offset` days from today (local). */
const d = (offset) => {
  const base = new Date();
  base.setHours(12, 0, 0, 0); // noon avoids any DST edge
  base.setDate(base.getDate() + offset);
  return toIso(base);
};
const WEEKDAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
/** abbreviated weekday code (frozen teaching module format) for d(offset). */
const dow = (offset) => WEEKDAYS[new Date(`${d(offset)}T12:00:00`).getDay()];
const monthHeading = (iso, deltaMonths) => {
  const [y, m] = iso.split("-").map(Number);
  return new Date(y, m - 1 + deltaMonths, 1).toLocaleDateString("en-IN", {
    month: "long",
    year: "numeric",
  });
};
/** Mirror calendar-utils formatDay / formatLong + chip rendering for parity asserts. */
const fmtDay = (iso) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("en-IN", {
    weekday: "short", day: "numeric", month: "short",
  });
const fmtLong = (iso) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("en-IN", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
const chipText = (item) => (item.start_time ? `${item.start_time} ` : "") + item.title;
const startOfWeekIso = (iso) => {
  const base = new Date(`${iso}T12:00:00`);
  base.setDate(base.getDate() - ((base.getDay() + 6) % 7));
  return toIso(base);
};

// ---------------------------------------------------------------- stamps
const STAMP = Date.now().toString(36);
const L = (label) => `${label} E2E ${STAMP}`;
const CLASS_TITLE = L("Graph Theory");
const STUDENT_NAME = L("Nikhil Rao");
const ASSIGNMENT_TITLE = L("Problem Set 7");
const EVENT_TODAY = L("Staff Briefing");
const EVENT_COLLOQUIUM = L("Colloquium");
const EVENT_MEETING = L("Review Meet");
const COMMITTEE_NAME = L("IQAC Cell");
const MEETING_TITLE = L("IQAC Huddle");
const ACTION_TITLE = L("Upload AQAR annexure");
const PROJECT_TITLE = L("Tensor Methods");
const MILESTONE_TITLE = L("Midterm review");
const GRANT_TITLE = L("DST Startup Grant");
const VENDOR_NAME = L("Nirmal Books");
const PROPOSAL_TITLE = L("Library Books");
const TASK_DUE_DONE = L("Renew library membership");
const TASK_TOMORROW = L("Call India office");
const TASK_NEXT_WEEK = L("Draft budget note");
const TASK_NEXT_MONTH = L("Plan term break reading");
const TASK_OVERDUE_DONE = L("File old reimbursements");
const ENTRY_YOGA = L("Wellness yoga");
const ENTRY_MEDICAL = L("Dental appointment");
const ENTRY_SESSION = L("Mentoring session");
const NOTIF_BELL = L("Reminder bell");
const NOTIF_NUDGE = L("Quiet nudge");
const NOTIF_MANUAL = L("Manual note");
const NOTIF_READ = L("Already read nudge");

const TODAY = d(0);
const EXPECTED_TASKS_AFTER_CRUD = 5; // due-done d0, tomorrow d1 (completed), edited d1, d30, UI-created

// ---------------------------------------------------------------- helpers
const postJson = (path, body, method = "POST") =>
  fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

const getJson = (path) =>
  fetch(`${API}${path}`).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({}) ) }));

async function waitForText(page, text, timeoutMs = 15_000) {
  await page.waitForFunction(
    (wanted) => document.body.innerText.includes(wanted),
    { timeout: timeoutMs },
    text,
  );
  return true;
}

/** wait until `selector` element's text contains `text`. */
async function waitForSectionText(page, selector, text, timeoutMs = 15_000) {
  await page.waitForFunction(
    (sel, wanted) => {
      const el = document.querySelector(sel);
      return !!el && el.textContent.includes(wanted);
    },
    { timeout: timeoutMs },
    selector,
    text,
  );
  return true;
}

/** wait until `selector` element's text does NOT contain `text`. */
async function waitForSectionGone(page, selector, text, timeoutMs = 15_000) {
  await page.waitForFunction(
    (sel, wanted) => {
      const el = document.querySelector(sel);
      return !el || !el.textContent.includes(wanted);
    },
    { timeout: timeoutMs },
    selector,
    text,
  );
  return true;
}

async function waitForGone(page, selector, timeoutMs = 15_000) {
  await page.waitForFunction(
    (sel) => !document.querySelector(sel),
    { timeout: timeoutMs },
    selector,
  );
  return true;
}

const sectionText = (page, selector) =>
  page.evaluate((sel) => document.querySelector(sel)?.textContent ?? null, selector);

/** click a link by its exact visible label. */
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

/** Read the big value of a dashboard card by its label. */
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

/** Wait until all six PART 6 cards show numeric values. */
async function waitForDashboard(page) {
  await page.waitForFunction(
    () => {
      const labels = [
        "Today's Tasks", "Deadlines (7d)", "Meetings (7d)",
        "Unread Nudges", "Overdue", "Done Today",
      ];
      const cards = [...document.querySelectorAll(".rounded-xl")];
      return labels.every((label) =>
        cards.some((card) => {
          const labelEl = [...card.querySelectorAll("div")].find(
            (el) => el.textContent?.trim().toUpperCase() === label.toUpperCase(),
          );
          const value = card.querySelector("p")?.textContent?.trim() ?? "";
          return labelEl && /^\d+$/.test(value);
        }),
      );
    },
    { timeout: 30_000 },
  );
}

async function readDashboardCards(page) {
  await waitForDashboard(page);
  const labels = [
    "Today's Tasks", "Deadlines (7d)", "Meetings (7d)",
    "Unread Nudges", "Overdue", "Done Today",
  ];
  const values = await Promise.all(labels.map((label) => cardValue(page, label)));
  return {
    todays_tasks: Number.parseInt(values[0] ?? "NaN", 10),
    upcoming_deadlines: Number.parseInt(values[1] ?? "NaN", 10),
    upcoming_meetings: Number.parseInt(values[2] ?? "NaN", 10),
    unread_notifications: Number.parseInt(values[3] ?? "NaN", 10),
    overdue_items: Number.parseInt(values[4] ?? "NaN", 10),
    completed_today: Number.parseInt(values[5] ?? "NaN", 10),
  };
}

/** Click one of the hub tabs (Overview/Calendar/Tasks/Notifications/Search). */
async function selectHubTab(page, id) {
  const clicked = await page.evaluate((tabId) => {
    const tab = document.getElementById(`productivity-tab-${tabId}`);
    if (!tab) return false;
    tab.click();
    return true;
  }, id);
  if (!clicked) throw new Error(`Hub tab ${id} missing`);
}

/** Click a role=tab by label inside a scope selector (case-insensitive; a
 * trailing `*` switches to startsWith — needed for tabs carrying counter
 * chips, e.g. "Unread 3" whose textContent includes the count). */
async function clickTab(page, scope, label) {
  const clicked = await page.evaluate(
    (sel, wanted) => {
      const root = document.querySelector(sel) ?? document;
      const star = wanted.endsWith("*");
      const needle = (star ? wanted.slice(0, -1) : wanted).toLowerCase();
      const tab = [...root.querySelectorAll('[role="tab"]')].find((el) => {
        const text = (el.textContent?.trim() ?? "").toLowerCase();
        return star ? text.startsWith(needle) : text === needle;
      });
      if (!tab) return false;
      tab.click();
      return true;
    },
    scope,
    label,
  );
  if (!clicked) throw new Error(`Tab “${label}” in ${scope} missing`);
}

/** Click a button by aria-label (optionally scoped). */
async function clickAria(page, ariaLabel, scope = null) {
  const clicked = await page.evaluate(
    (wanted, sel) => {
      const root = (sel && document.querySelector(sel)) || document;
      const button = [...root.querySelectorAll(`button[aria-label="${wanted}"]`)][0];
      if (!button) return false;
      button.click();
      return true;
    },
    ariaLabel,
    scope,
  );
  if (!clicked) throw new Error(`Button aria-label “${ariaLabel}” missing`);
  return true;
}

/** Click a button containing visible text (optionally scoped). */
async function clickTextButton(page, text, scope = null) {
  const clicked = await page.evaluate(
    (wanted, sel) => {
      const root = (sel && document.querySelector(sel)) || document;
      const button = [...root.querySelectorAll("button")].find(
        (el) => el.textContent?.trim() === wanted,
      );
      if (!button) return false;
      button.click();
      return true;
    },
    text,
    scope,
  );
  if (!clicked) throw new Error(`Button “${text}” missing`);
}

/** Set a controlled input's value the React-safe way. */
async function setInputValue(page, selector, value) {
  await page.waitForSelector(selector, { timeout: 15_000 });
  await page.evaluate(
    (sel, val) => {
      const el = document.querySelector(sel);
      if (!el) throw new Error(`input ${sel} missing`);
      const prototype = el instanceof HTMLTextAreaElement
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

/** Accept the next native dialog (confirm/prompt) with an optional value. */
function armDialog(page, value) {
  page.once("dialog", (dialog) => {
    void dialog.accept(value ?? "");
  });
}

const TASKS_SECTION = 'section[aria-label="Personal tasks"]';
const CENTER_SECTION = 'section[aria-label="Notification center"]';

/** The center renders skeleton cards (list unmounted) during every refetch;
 * wait until the rows list is mounted again before clicking anything. */
async function waitNotifRows(page, timeoutMs = 15_000) {
  await page.waitForFunction(
    (sel) => !!document.querySelector(sel)?.querySelector('ul[aria-label="Notification list"]'),
    { timeout: timeoutMs },
    CENTER_SECTION,
  );
}
const CAL_SECTION = 'section[aria-label="Productivity calendar"]';
const ENTRIES_SECTION = 'section[aria-label="Personal calendar entries"]';

// ------------------------------------------------------------------ seed
async function seed() {
  const ids = {};
  let r = await postJson("/students", {
    name: STUDENT_NAME, student_type: "ug", roll_number: `E2E-${STAMP}-ST`,
    uploaded_by: "e2e:productivity", department: "Mathematics",
    programme: "BSc Mathematics", semester: 3,
  });
  if (r.status !== 201) throw new Error(`student seed: ${r.status} ${JSON.stringify(r.body)}`);
  ids.student = r.body.id;

  r = await postJson("/teaching/classes", {
    title: CLASS_TITLE, uploaded_by: "e2e:productivity", course_code: `M101-${STAMP}`,
    programme: "BSc Mathematics", semester: 3, credits: 4,
    students: [ids.student],
    weekly_schedule: [{ day: dow(0), start: "09:00", end: "10:00" }],
  });
  if (r.status !== 201) throw new Error(`class seed: ${r.status} ${JSON.stringify(r.body)}`);
  ids.class = r.body.id;

  r = await postJson(`/teaching/classes/${ids.class}/attendance`, {
    session_date: TODAY, records: { [ids.student]: "present" }, actor: "e2e:productivity",
  });
  if (r.status !== 201) throw new Error(`attendance seed: ${r.status} ${JSON.stringify(r.body)}`);

  r = await postJson("/teaching/assignments", {
    title: ASSIGNMENT_TITLE, uploaded_by: "e2e:productivity", class_id: ids.class,
    assignment_type: "assignment", max_marks: 20, deadline: d(4), weightage: 10,
  });
  if (r.status !== 201) throw new Error(`assignment seed: ${r.status} ${JSON.stringify(r.body)}`);
  ids.assignment = r.body.id;

  for (const [title, offset] of [[EVENT_TODAY, 0], [EVENT_COLLOQUIUM, 2], [EVENT_MEETING, 6]]) {
    r = await postJson("/events", {
      title, uploaded_by: "e2e:productivity", event_type: "custom",
      event_status: "planned", start_date: d(offset),
      venue: offset === 2 ? "Seminar Hall A" : undefined,
    });
    if (r.status !== 201) throw new Error(`event seed(${title}): ${r.status} ${JSON.stringify(r.body)}`);
    if (offset === 2) ids.colloquium = r.body.id;
  }

  r = await postJson("/committees", {
    name: COMMITTEE_NAME, uploaded_by: "e2e:productivity", committee_code: `E2E-${STAMP}-IQ`,
    committee_type: "Internal Quality Assurance Cell (IQAC)",
  });
  if (r.status !== 201) throw new Error(`committee seed: ${r.status} ${JSON.stringify(r.body)}`);
  ids.committee = r.body.id;

  r = await postJson(`/committees/${ids.committee}/meetings`, {
    title: MEETING_TITLE, uploaded_by: "e2e:productivity", meeting_number: "1",
    meeting_date: d(10), mode: "offline",
  });
  if (r.status !== 201) throw new Error(`meeting seed: ${r.status} ${JSON.stringify(r.body)}`);
  ids.meeting = r.body.id;

  r = await postJson(`/committees/meetings/${ids.meeting}/actions`, {
    title: ACTION_TITLE, status: "pending", due_date: d(-2), priority: "high",
    uploaded_by: "e2e:productivity",
  });
  if (r.status !== 201) throw new Error(`action seed: ${r.status} ${JSON.stringify(r.body)}`);
  ids.action = r.body.id;

  r = await postJson("/research/projects", {
    title: PROJECT_TITLE, uploaded_by: "e2e:productivity", lifecycle_status: "active",
    project_code: `E2E-${STAMP}-PR`, start_date: d(-5), end_date: d(3),
  });
  if (r.status !== 201) throw new Error(`project seed: ${r.status} ${JSON.stringify(r.body)}`);
  ids.project = r.body.id;

  r = await postJson(`/research/projects/${ids.project}/milestones`, {
    title: MILESTONE_TITLE, date: d(3), status: "pending", uploaded_by: "e2e:productivity",
  });
  if (r.status !== 201) throw new Error(`milestone seed: ${r.status} ${JSON.stringify(r.body)}`);
  ids.milestone = r.body.id;

  r = await postJson("/research/grants", {
    title: GRANT_TITLE, grant_number: `E2E-${STAMP}-GR`, uploaded_by: "e2e:productivity",
    amount: 120000, links: { projects: [ids.project] },
  });
  if (r.status !== 201) throw new Error(`grant seed: ${r.status} ${JSON.stringify(r.body)}`);
  ids.grant = r.body.id;

  r = await postJson(`/research/grants/${ids.grant}/installments`, {
    installment_no: 1, date: d(-1), amount: 40000, status: "scheduled",
    uploaded_by: "e2e:productivity",
  });
  if (r.status !== 201) throw new Error(`installment seed: ${r.status} ${JSON.stringify(r.body)}`);

  r = await postJson("/finance/vendors", { name: VENDOR_NAME, uploaded_by: "e2e:productivity" });
  if (r.status !== 201) throw new Error(`vendor seed: ${r.status} ${JSON.stringify(r.body)}`);
  ids.vendor = r.body.id;

  r = await postJson("/finance/proposals", {
    title: PROPOSAL_TITLE, uploaded_by: "e2e:productivity", proposal_number: `E2E-${STAMP}-PP`,
    proposal_date: d(-3), proposal_status: "approved", estimated_cost: 60000,
    purchase_orders: [{ po_number: `E2E-${STAMP}-PO`, amount: "30000",
                        vendor_id: ids.vendor, status: "issued", delivery_date: d(5) }],
    bills: [{ bill_number: `E2E-${STAMP}-B`, amount: "28000", gst_amount: "1400",
              payment_status: "pending", vendor_id: ids.vendor, bill_date: d(7) }],
  });
  if (r.status !== 201) throw new Error(`proposal seed: ${r.status} ${JSON.stringify(r.body)}`);
  ids.proposal = r.body.id;

  // ----- productivity domain objects through the NEW module's API
  const taskSeeds = [
    { title: TASK_DUE_DONE, due_date: TODAY, completed: true },
    { title: TASK_TOMORROW, due_date: d(1), priority: "high" },
    { title: TASK_NEXT_WEEK, due_date: d(7), priority: "medium", category: "finance" },
    { title: TASK_NEXT_MONTH, due_date: d(30) },
    { title: TASK_OVERDUE_DONE, due_date: d(-2), completed: true },
  ];
  for (const seedTask of taskSeeds) {
    r = await postJson("/productivity/tasks", { ...seedTask, uploaded_by: "e2e:productivity" });
    if (r.status !== 201) throw new Error(`task seed(${seedTask.title}): ${r.status} ${JSON.stringify(r.body)}`);
    if (seedTask.title === TASK_NEXT_WEEK) ids.nextWeekTask = r.body.id;
    if (seedTask.title === TASK_TOMORROW) ids.tomorrowTask = r.body.id;
  }

  for (const [title, offset] of [[ENTRY_YOGA, 3], [ENTRY_MEDICAL, 8], [ENTRY_SESSION, 2]]) {
    r = await postJson("/productivity/calendar-entries", {
      title, uploaded_by: "e2e:productivity", start_date: d(offset),
      location: title === ENTRY_YOGA ? "Community Hall" : undefined,
    });
    if (r.status !== 201) throw new Error(`entry seed(${title}): ${r.status} ${JSON.stringify(r.body)}`);
    if (title === ENTRY_SESSION) ids.sessionEntry = r.body.id;
  }

  for (const notif of [
    { title: NOTIF_BELL, body: "Quiet nudge body", category: "deadline", priority: "high", read: false },
    { title: NOTIF_NUDGE, body: "Nudge yourself", category: "task", priority: "medium", read: false },
    { title: NOTIF_MANUAL, body: "Manual note body", category: "system", priority: "low", read: false },
    { title: NOTIF_READ, body: "Nothing new", category: "meeting", priority: "low", read: true },
  ]) {
    const { read } = notif;
    const payload = { ...notif };
    delete payload.read;
    r = await postJson("/productivity/notifications", { ...payload, uploaded_by: "e2e:productivity" });
    if (r.status !== 201) throw new Error(`notification seed(${notif.title}): ${r.status} ${JSON.stringify(r.body)}`);
    if (read) {
      // notifications are created unread by contract; mark-read via the update route
      const put = await postJson(`/productivity/notifications/${r.body.id}`, {
        is_read: true, uploaded_by: "e2e:productivity",
      }, "PUT");
      if (put.status !== 200 || put.body.is_read !== true) {
        throw new Error(`notification read-mark seed: ${put.status} ${JSON.stringify(put.body)}`);
      }
    }
  }
  return ids;
}

// ------------------------------------------------------------------ main
async function main() {
  // --- API baselines BEFORE seeding (shared global counters)
  const dashBase = (await getJson("/productivity/dashboard")).body;
  const notifBase = (await getJson("/productivity/notifications?page_size=1")).body;
  check("seed: baselines captured",
    typeof dashBase.todays_tasks === "number" && typeof notifBase.total_count === "number",
    `${JSON.stringify(dashBase)} active=${notifBase.total_count} unread=${notifBase.unread_count}`);
  let expectedActive = notifBase.total_count;
  let expectedUnread = notifBase.unread_count;

  const ids = await seed();
  check("seed: dated world created through frozen + productivity APIs", !!ids.proposal);
  expectedActive += 4;
  expectedUnread += 3;

  // --- PART 5 engine: first sweep creates; second sweep is a no-op (dedupe)
  const r1 = (await postJson("/productivity/notifications/refresh", { uploaded_by: "e2e:productivity" })).body;
  check("engine: first sweep generates automatic reminders",
    r1.created >= 5 && r1.considered === r1.created + r1.skipped_existing,
    JSON.stringify(r1));
  expectedActive += r1.created;
  expectedUnread += r1.created;
  const r2 = (await postJson("/productivity/notifications/refresh", { uploaded_by: "e2e:productivity" })).body;
  check("engine: second sweep is idempotent (dedupe by source key)",
    r2.created === 0 && r2.skipped_existing === r2.considered, JSON.stringify(r2));

  // --- API recount parity after seed
  {
    const now = (await getJson("/productivity/notifications?page_size=1")).body;
    check("api: notification center counts match tracked expectations",
      now.total_count === expectedActive && now.unread_count === expectedUnread,
      `${now.total_count}/${now.unread_count} vs ${expectedActive}/${expectedUnread}`);
  }

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
    // ------------------------------------------------ sidebar -> hub
    await page.goto(`${BASE}/events`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Events & Academic Activities", 30_000);
    await clickLinkWithText(page, "Productivity");
    await waitForText(page, "Productivity Hub", 30_000);
    check("sidebar: Productivity entry navigates to the hub", page.url().endsWith("/productivity"));

    // ------------------------------------------------ Overview tab (PART 6)
    const cards = await readDashboardCards(page);
    check("overview: six PART 6 cards render with numeric values",
      Object.values(cards).every((value) => Number.isInteger(value)), JSON.stringify(cards));
    const expectSeeded = (key, delta, label) =>
      check(`overview: ${label} = baseline ${dashBase[key]} + ${delta}`,
        cards[key] === dashBase[key] + delta, `${cards[key]} vs ${dashBase[key] + delta}`);
    expectSeeded("todays_tasks", 0, "Today's Tasks (only the seeded today-task, already done → hidden)");
    expectSeeded("upcoming_deadlines", 6,
      "Deadlines (7d): task d+1, task d+7, assignment d+4, milestone d+3, PO d+5, bill d+7");
    expectSeeded("upcoming_meetings", 3, "Meetings (7d): events d0/d+2/d+6");
    check("overview: Unread Nudges = baseline + 3 own + engine sweep",
      cards.unread_notifications === dashBase.unread_notifications + 3 + r1.created,
      `${cards.unread_notifications} vs ${dashBase.unread_notifications + 3 + r1.created}`);
    expectSeeded("overdue_items", 2, "Overdue: committee action d-2 + installment d-1");
    expectSeeded("completed_today", 2, "Done Today: two seeded tasks completed at seed time");
    const dashNow = (await getJson("/productivity/dashboard")).body;
    check("api: dashboard parity with the rendered cards",
      dashNow.todays_tasks === cards.todays_tasks &&
      dashNow.upcoming_deadlines === cards.upcoming_deadlines &&
      dashNow.upcoming_meetings === cards.upcoming_meetings &&
      dashNow.unread_notifications === cards.unread_notifications &&
      dashNow.overdue_items === cards.overdue_items &&
      dashNow.completed_today === cards.completed_today,
      JSON.stringify(dashNow));

    // ------------------------------------------------ PART 5 reminder buckets
    const remindersApi = (await getJson("/productivity/reminders")).body;
    check("reminders api: five buckets returned",
      ["overdue", "due_today", "upcoming_today", "tomorrow", "this_week"].every((key) =>
        Array.isArray(remindersApi[key])));
    for (const [bucket, title] of [
      ["overdue", ACTION_TITLE],
      ["overdue", "Installment #1"],
      ["upcoming_today", EVENT_TODAY],
      ["upcoming_today", CLASS_TITLE],
      ["tomorrow", TASK_TOMORROW],
      ["this_week", TASK_NEXT_WEEK],
      ["this_week", ASSIGNMENT_TITLE],
      ["this_week", MILESTONE_TITLE],
      ["this_week", `PO E2E-${STAMP}-PO delivery`],
      ["this_week", `Bill E2E-${STAMP}-B payable`],
    ]) {
      await waitForSectionText(page, `section[aria-label="${bucket === "overdue" ? "Overdue" : bucket === "due_today" ? "Due today" : bucket === "upcoming_today" ? "Upcoming today" : bucket === "tomorrow" ? "Tomorrow" : "This week"}"]`, title);
      check(`reminders: “${title}” listed under ${bucket}`, true);
    }
    check("reminders api: seeded items land in the same buckets",
      remindersApi.overdue.some((item) => item.title === ACTION_TITLE) &&
      remindersApi.tomorrow.some((item) => item.title === TASK_TOMORROW) &&
      remindersApi.upcoming_today.some((item) => item.title === CLASS_TITLE) &&
      remindersApi.this_week.some((item) => item.title === ASSIGNMENT_TITLE));
    check("reminders: completed overdue task is NOT resurfaced",
      !remindersApi.overdue.some((item) => item.title === TASK_OVERDUE_DONE) &&
      !(await sectionText(page, 'section[aria-label="Overdue"]'))?.includes(TASK_OVERDUE_DONE));
    check("reminders api: report-duty action carries its due date",
      remindersApi.overdue.find((item) => item.title === ACTION_TITLE)?.date === d(-2));

    // ------------------------------------------------ Calendar tab
    await selectHubTab(page, "calendar");
    await page.waitForSelector(CAL_SECTION, { timeout: 15_000 });
    check("calendar: workspace renders (PART 1 shell)", true);

    // API feed for the exact month window the UI shows
    const matrixFrom = (() => {
      const first = `${TODAY.slice(0, 8)}01`;
      const base = new Date(`${first}T12:00:00`);
      const offset = (base.getDay() + 6) % 7;
      const start = new Date(base);
      start.setDate(start.getDate() - offset);
      const end = new Date(start);
      end.setDate(end.getDate() + 41);
      return { from: toIso(start), to: toIso(end) };
    })();
    const feed = (await getJson(`/productivity/calendar?date_from=${matrixFrom.from}&date_to=${matrixFrom.to}`)).body;
    const stampItems = (feed.items ?? []).filter((item) => item.title.includes(STAMP));
    check("calendar api: aggregated feed carries every seeded source",
      ["events", "committee_meetings", "research_projects", "grant_milestones", "teaching",
       "assignments", "attendance_sessions", "finance_due", "reports_due", "personal"].every((src) =>
        src === "committee_meetings" || stampItems.some((item) => item.source === src)),
      stampItems.map((item) => `${item.source}:${item.title}`).join(" | "));

    // Month view: structural per-cell parity with the API feed — every cell
    // renders exactly the first ≤3 feed items as chips plus the "+N more"
    // overflow marker (deterministic on any database, crowded days included).
    const cells = await page.evaluate((sel) =>
      [...document.querySelectorAll(`${sel} [data-date]`)].map((cell) => ({
        date: cell.getAttribute("data-date"),
        chips: [...cell.querySelectorAll("a")].map((anchor) =>
          (anchor.textContent ?? "").replace(/\s+/g, " ").trim()),
        more: /\+(\d+) more/.exec(cell.textContent ?? "")?.[1] ?? null,
      })),
      CAL_SECTION,
    );
    {
      const byDate = {};
      for (const item of feed.items ?? []) (byDate[item.date] ??= []).push(item);
      let parity = true;
      for (const cell of cells) {
        const items = byDate[cell.date] ?? [];
        const expectedChips = items.slice(0, 3).map(chipText);
        if (JSON.stringify(cell.chips) !== JSON.stringify(expectedChips)) parity = false;
        const expectedMore = items.length > 3 ? String(items.length - 3) : null;
        if (cell.more !== expectedMore) parity = false;
      }
      check("calendar: month grid = API feed per cell (chips, order, +N overflow)",
        parity && cells.length >= 28, `${cells.length} cells compared`);
    }
    check("calendar: month grid has Monday-first matrix header",
      await page.evaluate((sel) => {
        const root = document.querySelector(sel);
        return !!root && [...root.querySelectorAll("div")].some((el) =>
          el.childElementCount === 7 && (el.textContent ?? "").startsWith("MonTueWedThuFriSatSun"));
      }, CAL_SECTION));

    // Agenda view: every STAMP title in the 30-day window is listed
    await clickTab(page, CAL_SECTION, "Agenda");
    await page.waitForSelector(`${CAL_SECTION} [aria-label="Agenda"]`, { timeout: 15_000 });
    const agendaFeed = (await getJson(`/productivity/calendar?date_from=${TODAY}&date_to=${d(29)}`)).body;
    let agendaOk = true;
    for (const item of (agendaFeed.items ?? []).filter((entry) => entry.title.includes(STAMP))) {
      const present = await page.evaluate(
        (sel, wanted) => document.querySelector(sel)?.textContent.includes(wanted) ?? false,
        `${CAL_SECTION} [aria-label="Agenda"]`,
        item.title,
      );
      if (!present) agendaOk = false;
    }
    check("calendar: agenda lists every upcoming STAMP item (UI = API parity)", agendaOk);
    check("calendar: agenda shows source + subtitle context",
      (await sectionText(page, `${CAL_SECTION} [aria-label="Agenda"]`))?.includes("Seminar Hall A") === true);

    // Source chips — exercised in Agenda view because it has no per-day chip
    // cap (the month view trims crowded days to 3 chips + "+N more", which is
    // data-dependent on a shared database).
    const AGENDA_SEL = `${CAL_SECTION} [aria-label="Agenda"]`;
    await clickTextButton(page, "Personal", `${CAL_SECTION} fieldset`);
    await waitForSectionGone(page, AGENDA_SEL, ENTRY_YOGA);
    check("calendar: Personal source chip hides personal feed items", true);
    await clickTextButton(page, "Events", `${CAL_SECTION} fieldset`);
    await waitForSectionGone(page, AGENDA_SEL, EVENT_COLLOQUIUM);
    check("calendar: Events source chip hides event feed items", true);
    await clickTextButton(page, "Personal", `${CAL_SECTION} fieldset`);
    await waitForSectionText(page, AGENDA_SEL, ENTRY_YOGA);
    await clickTextButton(page, "Events", `${CAL_SECTION} fieldset`);
    await waitForSectionText(page, AGENDA_SEL, EVENT_COLLOQUIUM);
    check("calendar: re-enabling chips restores the items", true);

    // Week view: 7 day-columns, Today marker, per-column chips = feed slice
    await clickTab(page, CAL_SECTION, "Week");
    await page.waitForFunction(
      (sel) => document.querySelectorAll(`${sel} section`).length >= 7,
      { timeout: 15_000 },
      CAL_SECTION,
    );
    const weekText = (await sectionText(page, CAL_SECTION)) ?? "";
    {
      const weekCols = await page.evaluate((sel) =>
        [...document.querySelectorAll(`${sel} section`)].map((col) => ({
          label: col.getAttribute("aria-label") ?? "",
          chips: [...col.querySelectorAll("a")].map((anchor) =>
            (anchor.textContent ?? "").replace(/\s+/g, " ").trim()),
        })),
        CAL_SECTION,
      );
      const monday = startOfWeekIso(TODAY);
      let parity = weekCols.length === 7;
      for (let index = 0; index < 7 && parity; index += 1) {
        const date = new Date(`${monday}T12:00:00`);
        date.setDate(date.getDate() + index);
        const iso = toIso(date);
        const items = (feed.items ?? []).filter((item) => item.date === iso);
        const expected = items.slice(0, 6).map(chipText);
        if (JSON.stringify(weekCols[index]?.chips ?? null) !== JSON.stringify(expected)) {
          parity = false;
        }
      }
      check("calendar: week view per-column chips = feed slice (cap-6 contract)",
        parity, `${weekCols.length} columns`);
    }
    check("calendar: week view carries the Today marker", weekText.includes("Today"));

    // Day view: single column; chips = first 6 feed items of today
    await clickTab(page, CAL_SECTION, "Day");
    await page.waitForFunction(
      () => {
        const root = document.querySelector('section[aria-label="Productivity calendar"]');
        return !!root && root.querySelectorAll("section").length === 1;
      },
      { timeout: 15_000 },
    );
    {
      const dayChips = await page.evaluate((sel) => {
        const root = document.querySelector(sel);
        const col = root?.querySelector("section");
        return [...(col?.querySelectorAll("a") ?? [])].map((anchor) =>
          (anchor.textContent ?? "").replace(/\s+/g, " ").trim());
      }, CAL_SECTION);
      const expected = (feed.items ?? [])
        .filter((item) => item.date === TODAY)
        .slice(0, 6)
        .map(chipText);
      check("calendar: day view chips = today's feed slice (cap-6 contract)",
        JSON.stringify(dayChips) === JSON.stringify(expected),
        dayChips.join(" | ").slice(0, 140));
    }

    // Navigation: Next month → heading shifts; Today button → back
    await clickTab(page, CAL_SECTION, "Month");
    await page.waitForSelector(`${CAL_SECTION} [data-date]`, { timeout: 15_000 });
    await waitForSectionText(page, CAL_SECTION, monthHeading(TODAY, 0));
    await clickAria(page, "Next", CAL_SECTION);
    await waitForSectionText(page, CAL_SECTION, monthHeading(TODAY, 1));
    check("calendar: Next navigates to the following month", true);
    await clickTextButton(page, "Today", CAL_SECTION);
    await waitForSectionText(page, CAL_SECTION, monthHeading(TODAY, 0));
    check("calendar: Today button returns to the current month", true);

    // ---- personal entries list (PART 2 tail)
    await waitForSectionText(page, ENTRIES_SECTION, ENTRY_YOGA);
    const entriesSectionText = (await sectionText(page, ENTRIES_SECTION)) ?? "";
    check("entries: list renders all three seeded entries",
      entriesSectionText.includes(ENTRY_YOGA) &&
      entriesSectionText.includes(ENTRY_MEDICAL) &&
      entriesSectionText.includes(ENTRY_SESSION));
    const entriesCount = entriesSectionText.match(/(\d+) entr/);
    check("entries: list shows location + a sane count",
      entriesSectionText.includes("Community Hall") &&
      !!entriesCount && Number.parseInt(entriesCount[1], 10) >= 3,
      entriesSectionText.split("\n")[0]);

    // Create via the calendar's own Add entry affordance (pre-fills cursor date)
    await clickTextButton(page, "Add entry", CAL_SECTION);
    await page.waitForSelector('[role="dialog"]', { timeout: 15_000 });
    const prefilled = await page.evaluate(
      () => document.querySelector('input[aria-label="Entry start date"]')?.value ?? null,
    );
    check("entries: Add entry opens modal with the cursor date prefilled", prefilled === TODAY, prefilled ?? "none");
    await setInputValue(page, 'input[aria-label="Entry title"]', L("Evening walk"));
    await setInputValue(page, 'input[aria-label="Entry location"]', "Campus loop");
    await clickTextButton(page, "Create entry");
    await waitForGone(page, '[role="dialog"]');
    await waitForSectionText(page, ENTRIES_SECTION, L("Evening walk"));
    check("entries: created entry lands in the personal list", true);

    // Edit the mentoring session: push it to d+4 (span renders formatted dates)
    await clickAria(page, `Edit: ${ENTRY_SESSION}`, ENTRIES_SECTION);
    await page.waitForSelector('[role="dialog"]', { timeout: 15_000 });
    await setInputValue(page, 'input[aria-label="Entry end date"]', d(4));
    await clickTextButton(page, "Save changes");
    await waitForGone(page, '[role="dialog"]');
    await page.waitForFunction(
      (sel, title, span) => {
        const row = [...document.querySelectorAll(`${sel} li`)].find((li) =>
          li.getAttribute("aria-label") === title);
        return !!row && row.textContent.includes(span);
      },
      { timeout: 15_000 },
      ENTRIES_SECTION,
      ENTRY_SESSION,
      `${fmtDay(d(2))} – ${fmtDay(d(4))}`,
    );
    check("entries: edited entry shows the new d+2 – d+4 span", true);

    // Delete the dental appointment
    armDialog(page); // confirm
    await clickAria(page, `Delete: ${ENTRY_MEDICAL}`, ENTRIES_SECTION);
    await page.waitForFunction(
      (sel, title) =>
        ![...document.querySelectorAll(`${sel} li`)].some((li) => li.getAttribute("aria-label") === title),
      { timeout: 15_000 },
      ENTRIES_SECTION,
      ENTRY_MEDICAL,
    );
    check("entries: deleted entry disappears from the list", true);

    // ------------------------------------------------ Tasks tab (PART 3)
    await selectHubTab(page, "tasks");
    await page.waitForSelector(TASKS_SECTION, { timeout: 15_000 });
    await setInputValue(page, `${TASKS_SECTION} input[aria-label="Search tasks"]`, STAMP);
    await waitForSectionText(page, TASKS_SECTION, TASK_TOMORROW);
    const stampedList = (await sectionText(page, TASKS_SECTION)) ?? "";
    check("tasks: STAMP filter lists all five seeded tasks",
      stampedList.includes(TASK_DUE_DONE) && stampedList.includes(TASK_TOMORROW) &&
      stampedList.includes(TASK_NEXT_WEEK) && stampedList.includes(TASK_NEXT_MONTH) &&
      stampedList.includes(TASK_OVERDUE_DONE) && stampedList.includes("5 tasks"));
    check("tasks: rows show due context, completion meta and priority badge",
      stampedList.includes(`Due ${d(1)}`) && stampedList.includes(`Done ${TODAY}`) &&
      stampedList.includes("High"));

    // Create the sixth task through the modal
    await clickTextButton(page, "New task", TASKS_SECTION);
    await page.waitForSelector('[role="dialog"]', { timeout: 15_000 });
    await setInputValue(page, 'input[aria-label="Task title"]', L("Book train tickets"));
    await setInputValue(page, 'textarea[aria-label="Task description"]', "Window seat preferred");
    await page.select('select[aria-label="Task category"]', "personal");
    await page.select('select[aria-label="Task priority"]', "medium");
    await clickTextButton(page, "Create task");
    await waitForGone(page, '[role="dialog"]');
    await waitForSectionText(page, TASKS_SECTION, L("Book train tickets"));
    check("tasks: modal-created task joins the filtered list (6 total)",
      ((await sectionText(page, TASKS_SECTION)) ?? "").includes("6 tasks"));

    // Edit: move “Draft budget note” from d+7 to d+1
    await clickAria(page, `Edit: ${TASK_NEXT_WEEK}`, TASKS_SECTION);
    await page.waitForSelector('[role="dialog"]', { timeout: 15_000 });
    await setInputValue(page, 'input[aria-label="Task due date"]', d(1));
    await clickTextButton(page, "Save changes");
    await waitForGone(page, '[role="dialog"]');
    await page.waitForFunction(
      (sel, title, day) => {
        const row = [...document.querySelectorAll(`${sel} li`)].find((li) =>
          li.getAttribute("aria-label") === title);
        return !!row && row.textContent.includes(`Due ${day}`);
      },
      { timeout: 15_000 },
      TASKS_SECTION,
      TASK_NEXT_WEEK,
      d(1),
    );
    check("tasks: edited due date (d+7 → d+1) persists in the row", true);

    // Pin toggle
    await clickAria(page, `Pin: ${TASK_NEXT_MONTH}`, TASKS_SECTION);
    await page.waitForSelector(`button[aria-label="Unpin: ${TASK_NEXT_MONTH}"]`, { timeout: 15_000 });
    check("tasks: pin toggles in place", true);

    // Complete the tomorrow task
    await clickAria(page, `Mark done: ${TASK_TOMORROW}`, TASKS_SECTION);
    await page.waitForSelector(`button[aria-label="Mark open: ${TASK_TOMORROW}"]`, { timeout: 15_000 });
    check("tasks: complete toggles in place (checkbox flips)", true);
    await page.select(`${TASKS_SECTION} select[aria-label="Filter by status"]`, "completed");
    await page.waitForFunction(
      (sel, title) => document.querySelector(sel)?.textContent.includes(title) ?? false,
      { timeout: 15_000 },
      TASKS_SECTION,
      TASK_TOMORROW,
    );
    check("tasks: completed-status filter lists the just-finished task", true);
    await page.select(`${TASKS_SECTION} select[aria-label="Filter by status"]`, "");
    await waitForSectionText(page, TASKS_SECTION, TASK_NEXT_MONTH);

    // Delete the overdue-completed task
    armDialog(page);
    await clickAria(page, `Delete: ${TASK_OVERDUE_DONE}`, TASKS_SECTION);
    await page.waitForFunction(
      (sel, title) =>
        ![...document.querySelectorAll(`${sel} li`)].some((li) => li.getAttribute("aria-label") === title),
      { timeout: 15_000 },
      TASKS_SECTION,
      TASK_OVERDUE_DONE,
    );
    await waitForSectionText(page, TASKS_SECTION, `${EXPECTED_TASKS_AFTER_CRUD} tasks`);
    check("tasks: deleted task disappears (5 remain)", true);

    // Overdue-only filter: nothing of ours remains overdue
    await page.evaluate((sel) => {
      const box = document.querySelector(`${sel} input[aria-label="Overdue only"]`);
      box?.click();
    }, TASKS_SECTION);
    await sleep(800);
    const overdueFiltered = (await sectionText(page, TASKS_SECTION)) ?? "";
    check("tasks: Overdue-only filter yields no STAMP rows after cleanup",
      !overdueFiltered.includes(STAMP));
    await page.evaluate((sel) => {
      const box = document.querySelector(`${sel} input[aria-label="Overdue only"]`);
      box?.click();
    }, TASKS_SECTION);
    await waitForSectionText(page, TASKS_SECTION, TASK_NEXT_MONTH);

    // ------------------------------------------------ Overview re-check
    await selectHubTab(page, "overview");
    const cardsAfter = await readDashboardCards(page);
    check("overview re-check: Deadlines drop to baseline + 5 (completed task leaves; d+1 edited, assignment, milestone, PO, bill remain)",
      cardsAfter.upcoming_deadlines === dashBase.upcoming_deadlines + 5,
      `${cardsAfter.upcoming_deadlines} vs ${dashBase.upcoming_deadlines + 5}`);
    check("overview re-check: Done Today = baseline + 2 (two seeded + UI-completed − the deleted one)",
      cardsAfter.completed_today === dashBase.completed_today + 2,
      `${cardsAfter.completed_today} vs ${dashBase.completed_today + 2}`);
    check("overview re-check: meetings/overdue/unread unchanged by task stories",
      cardsAfter.upcoming_meetings === dashBase.upcoming_meetings + 3 &&
      cardsAfter.overdue_items === dashBase.overdue_items + 2 &&
      cardsAfter.unread_notifications === dashBase.unread_notifications + 3 + r1.created);

    // ------------------------------------------------ Notifications tab (PART 4)
    await selectHubTab(page, "notifications");
    await page.waitForSelector(CENTER_SECTION, { timeout: 15_000 });
    await waitForSectionText(page, CENTER_SECTION, NOTIF_BELL);
    const counterText = (await sectionText(page, `${CENTER_SECTION} p`)) ?? "";
    const counter = counterText.match(/(\d+) notifications? · (\d+) unread/);
    check("center: header counter = tracked active/unread totals",
      !!counter &&
      Number.parseInt(counter[1], 10) === expectedActive &&
      Number.parseInt(counter[2], 10) === expectedUnread,
      counterText.split("\n")[0]);
    const centerText = (await sectionText(page, CENTER_SECTION)) ?? "";
    check("center: Active tab lists the four seeded notifications",
      centerText.includes(NOTIF_BELL) && centerText.includes(NOTIF_NUDGE) &&
      centerText.includes(NOTIF_MANUAL) && centerText.includes(NOTIF_READ));
    check("center: unread chip on the Unread tab shows the tracked count",
      (await page.evaluate(() => {
        const tab = [...document.querySelectorAll('[role="tab"]')].find(
          (el) => el.textContent?.trim().startsWith("Unread"));
        return tab?.textContent.replace(/\D+/g, " ").trim() ?? "";
      })) === String(expectedUnread));

    // pin the manual note
    await waitNotifRows(page);
    await clickAria(page, `Pin: ${NOTIF_MANUAL}`, CENTER_SECTION);
    await page.waitForSelector(`button[aria-label="Unpin: ${NOTIF_MANUAL}"]`, { timeout: 15_000 });
    check("center: pin toggles (button flips to Unpin)", true);

    // snooze the bell until d+2 — it leaves the Active shelf
    await waitNotifRows(page);
    armDialog(page, d(2));
    await clickAria(page, `Snooze: ${NOTIF_BELL}`, CENTER_SECTION);
    await page.waitForFunction(
      (sel, title) =>
        ![...document.querySelectorAll(`${sel} li`)].some((li) => li.getAttribute("aria-label") === title),
      { timeout: 15_000 },
      CENTER_SECTION,
      NOTIF_BELL,
    );
    expectedActive -= 1;
    expectedUnread -= 1;
    check("center: snoozed notification leaves the Active shelf", true);

    // mark the nudge read
    await waitNotifRows(page);
    await clickAria(page, `Mark read: ${NOTIF_NUDGE}`, CENTER_SECTION);
    await page.waitForSelector(`button[aria-label="Mark unread: ${NOTIF_NUDGE}"]`, { timeout: 15_000 });
    expectedUnread -= 1;
    check("center: mark-read flips to mark-unread", true);

    // archive the already-read nudge
    await waitNotifRows(page);
    await clickAria(page, `Archive: ${NOTIF_READ}`, CENTER_SECTION);
    await page.waitForFunction(
      (sel, title) =>
        ![...document.querySelectorAll(`${sel} li`)].some((li) => li.getAttribute("aria-label") === title),
      { timeout: 15_000 },
      CENTER_SECTION,
      NOTIF_READ,
    );
    expectedActive -= 1;
    check("center: archived notification leaves the Active shelf", true);

    // snoozed shelf holds the bell; unsnooze it back
    await clickTab(page, CENTER_SECTION, "Snoozed");
    await waitForSectionText(page, CENTER_SECTION, NOTIF_BELL);
    check("center: Snoozed tab lists the snoozed bell with its date",
      ((await sectionText(page, CENTER_SECTION)) ?? "").includes(`Snoozed until ${d(2)}`));
    await clickAria(page, `Unsnooze: ${NOTIF_BELL}`, CENTER_SECTION);
    await page.waitForFunction(
      (sel, title) =>
        ![...document.querySelectorAll(`${sel} li`)].some((li) => li.getAttribute("aria-label") === title),
      { timeout: 15_000 },
      CENTER_SECTION,
      NOTIF_BELL,
    );
    expectedActive += 1;
    expectedUnread += 1;
    check("center: unsnooze returns the bell to the active set", true);

    // Unread tab: manual + bell unread; the read nudge is absent
    await clickTab(page, CENTER_SECTION, "Unread*");
    await waitForSectionText(page, CENTER_SECTION, NOTIF_MANUAL);
    const unreadText = (await sectionText(page, CENTER_SECTION)) ?? "";
    check("center: Unread tab shows unread only (nudge excluded after mark-read)",
      unreadText.includes(NOTIF_MANUAL) && !unreadText.includes(NOTIF_NUDGE));

    // back to Active; manual note creation adds an unread notification
    await clickTab(page, CENTER_SECTION, "Active");
    await waitForSectionText(page, CENTER_SECTION, NOTIF_BELL);
    await clickTextButton(page, "New note", CENTER_SECTION);
    await page.waitForSelector(`${CENTER_SECTION} form[aria-label="New notification"]`, { timeout: 15_000 });
    await setInputValue(page, `${CENTER_SECTION} input[aria-label="Notification title"]`, L("Hall ticket printed"));
    await setInputValue(page, `${CENTER_SECTION} textarea[aria-label="Notification body"]`, "Collect from office");
    await page.select(`${CENTER_SECTION} select[aria-label="Notification category"]`, "deadline");
    await clickTextButton(page, "Add note", CENTER_SECTION);
    await waitForSectionText(page, CENTER_SECTION, L("Hall ticket printed"));
    expectedActive += 1;
    expectedUnread += 1;
    check("center: manual note lands on the Active shelf as unread", true);

    // PART 5 refresh through the UI: the d+7→d+1 task moved buckets → exactly 1 new
    await waitNotifRows(page);
    await clickAria(page, "Refresh notifications", CENTER_SECTION);
    await waitForSectionText(page, CENTER_SECTION, "Reminder sweep:");
    const sweepLine = ((await sectionText(page, CENTER_SECTION)) ?? "")
      .match(/Reminder sweep: (\d+) new, (\d+) already shown/);
    expectedActive += Number.parseInt(sweepLine?.[1] ?? "0", 10);
    expectedUnread += Number.parseInt(sweepLine?.[1] ?? "0", 10);
    check("center: engine refresh reports exactly one new reminder (moved-due-date task)",
      !!sweepLine && sweepLine[1] === "1" && Number.parseInt(sweepLine[2], 10) > 0,
      sweepLine ? sweepLine[0] : "no line");
    {
      const r3 = (await postJson("/productivity/notifications/refresh", { uploaded_by: "e2e:productivity" })).body;
      check("center: subsequent API sweep is a strict no-op", r3.created === 0, JSON.stringify(r3));
    }

    // delete the archived nudge from its shelf
    await clickTab(page, CENTER_SECTION, "Archived");
    await waitForSectionText(page, CENTER_SECTION, NOTIF_READ);
    armDialog(page);
    await clickAria(page, `Delete: ${NOTIF_READ}`, CENTER_SECTION);
    await page.waitForFunction(
      (sel, title) =>
        ![...document.querySelectorAll(`${sel} li`)].some((li) => li.getAttribute("aria-label") === title),
      { timeout: 15_000 },
      CENTER_SECTION,
      NOTIF_READ,
    );
    check("center: delete removes the archived notification", true);
    {
      const now = (await getJson("/productivity/notifications?page_size=1")).body;
      check("center: API recount parity after the whole UI story",
        now.total_count === expectedActive && now.unread_count === expectedUnread,
        `${now.total_count}/${now.unread_count} vs ${expectedActive}/${expectedUnread}`);
    }

    // ------------------------------------------------ Search tab (PART 7)
    await selectHubTab(page, "search");
    const searchSection = 'section[aria-label="Productivity search"]';
    await page.waitForSelector(searchSection, { timeout: 15_000 });
    const searchCount = async () =>
      ((await sectionText(page, searchSection)) ?? "").match(/(\d+) results?/);
    const searchTotal = async (params) =>
      (await getJson(`/productivity/search?${params}`)).body.total_count;

    // q=STAMP: counter parity with the API + every visible row is stamped
    await setInputValue(page, `${searchSection} input[aria-label="Search productivity"]`, STAMP);
    await page.waitForFunction(
      (sel) => /\d+ results?/.test(document.querySelector(sel)?.textContent ?? ""),
      { timeout: 15_000 },
      searchSection,
    );
    {
      const counter = await searchCount();
      const apiTotal = await searchTotal(`q=${STAMP}`);
      const nonStamped = await page.evaluate((sel, stamp) =>
        [...document.querySelectorAll(`${sel} ul[aria-label="Search results"] li`)]
          .filter((li) => !(li.textContent ?? "").includes(stamp)).length,
        searchSection,
        STAMP,
      );
      check("search: STAMP query counter = API total; first-page rows all stamped",
        !!counter && Number.parseInt(counter[1], 10) === apiTotal && nonStamped === 0,
        `${counter?.[1]} vs api ${apiTotal}, nonStamped=${nonStamped}`);
    }

    // source=tasks narrows to exactly the five surviving own tasks
    await page.select(`${searchSection} select[aria-label="Filter by source"]`, "tasks");
    await waitForSectionText(page, searchSection, TASK_NEXT_MONTH);
    const tasksOnly = (await sectionText(page, searchSection)) ?? "";
    check(`search: source=tasks narrows to exactly ${EXPECTED_TASKS_AFTER_CRUD} own tasks`,
      tasksOnly.includes(`${EXPECTED_TASKS_AFTER_CRUD} result`), tasksOnly.split("\n")[0]);

    // date window d0..d1 keeps the three today/tomorrow tasks
    await setInputValue(page, `${searchSection} input[aria-label="From date"]`, TODAY);
    await setInputValue(page, `${searchSection} input[aria-label="To date"]`, d(1));
    await page.waitForFunction(
      (sel) => document.querySelector(sel)?.textContent.includes("3 results") ?? false,
      { timeout: 15_000 },
      searchSection,
    );
    const windowed = (await sectionText(page, searchSection)) ?? "";
    check("search: date window keeps d0/d+1 task anchors only",
      windowed.includes(TASK_DUE_DONE) && windowed.includes(TASK_TOMORROW) &&
      windowed.includes(TASK_NEXT_WEEK) && !windowed.includes(TASK_NEXT_MONTH));

    // priority filter isolates the high-priority completed call
    await page.select(`${searchSection} select[aria-label="Filter by priority"]`, "high");
    await page.waitForFunction(
      (sel) => document.querySelector(sel)?.textContent.includes("1 result") ?? false,
      { timeout: 15_000 },
      searchSection,
    );
    check("search: priority=high isolates the single high-priority task",
      ((await sectionText(page, searchSection)) ?? "").includes(TASK_TOMORROW));
    await page.select(`${searchSection} select[aria-label="Filter by priority"]`, "");

    // source=notifications: exactly the four live stamped notifications
    await setInputValue(page, `${searchSection} input[aria-label="From date"]`, "");
    await setInputValue(page, `${searchSection} input[aria-label="To date"]`, "");
    await page.select(`${searchSection} select[aria-label="Filter by source"]`, "notifications");
    await waitForSectionText(page, searchSection, NOTIF_MANUAL);
    {
      const notifOnly = (await sectionText(page, searchSection)) ?? "";
      const apiTotal = await searchTotal(`q=${STAMP}&source=notifications`);
      check("search: source=notifications — counter = API total, own rows present",
        notifOnly.includes(`${apiTotal} result`) && notifOnly.includes(NOTIF_BELL) &&
        notifOnly.includes(NOTIF_MANUAL), `api ${apiTotal}`);
    }

    // source=calendar + d+1..d+3 window: UI counter = API total, own rows visible
    await setInputValue(page, `${searchSection} input[aria-label="From date"]`, d(1));
    await setInputValue(page, `${searchSection} input[aria-label="To date"]`, d(3));
    await page.select(`${searchSection} select[aria-label="Filter by source"]`, "calendar");
    await page.waitForFunction(
      (sel, title) => document.querySelector(sel)?.textContent.includes(title) ?? false,
      { timeout: 15_000 },
      searchSection,
      ENTRY_YOGA,
    );
    {
      const counter = await searchCount();
      const apiTotal = await searchTotal(`q=${STAMP}&source=calendar&date_from=${d(1)}&date_to=${d(3)}`);
      const calText = (await sectionText(page, searchSection)) ?? "";
      check("search: calendar lens in d+1..d+3 — counter = API total, own rows rendered",
        !!counter && Number.parseInt(counter[1], 10) === apiTotal &&
        calText.includes(EVENT_COLLOQUIUM) && calText.includes(MILESTONE_TITLE),
        `${counter?.[1]} vs api ${apiTotal}`);

      // dual lens: clearing the source filter adds the two d+1-anchored tasks
      await page.select(`${searchSection} select[aria-label="Filter by source"]`, "");
      await page.waitForFunction(
        (sel, title) => {
          const text = document.querySelector(sel)?.textContent ?? "";
          return text.includes(title) && /\d+ results?/.test(text);
        },
        { timeout: 15_000 },
        searchSection,
        TASK_NEXT_WEEK,
      );
      const widened = await searchCount();
      check("search: removing the source filter adds task-lens hits (dual-lens by design)",
        !!widened && Number.parseInt(widened[1], 10) > apiTotal,
        `${apiTotal} -> ${widened?.[1]}`);
    }

    // ------------------------------------------------ cleanliness gates
    check("cleanliness: no failed API call during the whole tour", failingApi.length === 0,
      failingApi.slice(0, 3).join(" | "));
    check("cleanliness: no console/page errors", consoleErrors.length === 0,
      consoleErrors.slice(0, 3).join(" | "));
  } catch (err) {
    check(`fatal: ${err.message}`, false);
    try {
      const fs = await import("node:fs");
      await page.screenshot({ path: "/tmp/productivity-failure.png", fullPage: true });
      fs.writeFileSync("/tmp/productivity-failure.txt", await page.content());
    } catch {
      /* ignore */
    }
  } finally {
    await browser.close();
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

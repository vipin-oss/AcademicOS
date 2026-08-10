/**
 * Committees & Meetings module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   committees hub (PART 8 dashboard cards + upcoming meetings) -> PART 9
 *   directory with token search and type/department/chairperson/status/
 *   meeting-year filters -> create via the modal (PART 2 members rows +
 *   PART 7 link pickers) -> duplicate code + duplicate triple 409s in the
 *   modal -> the workspace (members leadership-first, meetings, links,
 *   documents lens, audit) -> meeting create + duplicate-number 409 ->
 *   the meeting workspace (PART 4 agenda manager with supporting documents,
 *   attendance, minutes & decisions, PART 5 action tracker) -> dashboard
 *   re-check -> faculty committee lens -> delete cascade -> 404 state.
 *
 * The cross-module graph (faculty chair/member/external, student member,
 * project, grant, publication, document) is seeded through the FROZEN
 * modules' own APIs.
 *
 * Usage:
 *   node tests/committees-e2e.mjs         # http://localhost:3000
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
const CHAIR_NAME = `Dr. Nandini Rao E2E ${STAMP}`;
const MEMBER_NAME = `Prof. Arjun Mehta E2E ${STAMP}`;
const EXTERNAL_NAME = `Dr. Sara Ali E2E ${STAMP}`;
const STUDENT_NAME = `Vikram Singh E2E ${STAMP}`;
const CPC_NAME = `Central Procurement Committee E2E ${STAMP}`;
const CPC_CODE = `E2E-${STAMP}-PC1`;
const FIN_NAME = `Finance Committee E2E ${STAMP}`;
const FIN_CODE = `E2E-${STAMP}-FC1`;
const MODAL_NAME = `E2E Modal Committee ${STAMP}`;
const MODAL_CODE = `E2E-${STAMP}-MC1`;
const TRASH_NAME = `E2E Trash Committee ${STAMP}`;
const MEETING_TITLE = `7th Procurement Meeting E2E ${STAMP}`;
const MODAL_MEETING = `E2E Modal Meeting ${STAMP}`;
const ACTION_TITLE = `Circulate tender minutes E2E ${STAMP}`;
const FOLLOWUP_TITLE = `Follow up with vendor E2E ${STAMP}`;
const PROJECT_TITLE = `E2E Committee-Linked Project ${STAMP}`;
const GRANT_TITLE = `E2E Committee-Linked Grant ${STAMP}`;
const PUB_TITLE = `E2E Committee-Linked Publication ${STAMP}`;
const DOC_TITLE = `E2E Agenda Attachment ${STAMP}`;

const postJson = (path, body, method = "POST") =>
  fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

const getJson = (path) =>
  fetch(`${API}${path}`).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

/**
 * Poll a GET endpoint until `predicate(body)` holds. Panel saves all toast
 * the identical "Meeting saved successfully", so a text-only wait can
 * short-circuit on the PREVIOUS save's lingering toast — the API is the
 * source of truth for "the save actually landed".
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

/**
 * Click a button by its exact label. When a dialog is open, a button INSIDE
 * the dialog wins over a same-labelled page button (mirrors the other
 * module harnesses).
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

/**
 * Fill the input wrapped by the <label> whose text starts with `label`
 * (dialog-scoped when a dialog is open). Native setter — keyboard simulation
 * races with list-refresh re-renders.
 */
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

/** Set the <select> wrapped by the <label> whose text starts with `label`. */
async function selectInField(page, label, value) {
  const ok = await page.evaluate(
    (wanted, val) => {
      const scope = document.querySelector('form[role="dialog"]') ?? document;
      const target = [...scope.querySelectorAll("label")].find((el) =>
        el.textContent?.trim().startsWith(wanted),
      );
      const select = target?.querySelector("select");
      if (!select) return false;
      select.focus();
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLSelectElement.prototype,
        "value",
      ).set;
      setter.call(select, val);
      select.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    },
    label,
    value,
  );
  if (!ok) throw new Error(`No select labelled “${label}” found.`);
}

/**
 * Wait until `needle` appears in body.innerText (explicit sleep+evaluate
 * loop; case-insensitive because innerText applies CSS text-transform).
 */
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

/**
 * Wait until a <select> contains an option with `value` (picker options are
 * fetched asynchronously — page.select throws when the option is not there
 * yet).
 */
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

/** Read the big number of a PART 8 dashboard card by its label. */
async function cardValue(page, label) {
  return page.evaluate((wanted) => {
    const cards = [...document.querySelectorAll("div.rounded-xl")];
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
  // ---------------------------------------------------- seed via the real API
  const chair = await postJson("/faculty", {
    name: CHAIR_NAME,
    employee_id: `E2E-${STAMP}-CM1`,
    uploaded_by: "registrar:e2e",
    designation: "Professor",
    department: "Physics",
  }).then((r) => r.body);
  const member = await postJson("/faculty", {
    name: MEMBER_NAME,
    employee_id: `E2E-${STAMP}-CM2`,
    uploaded_by: "registrar:e2e",
    designation: "Associate Professor",
  }).then((r) => r.body);
  const external = await postJson("/faculty", {
    name: EXTERNAL_NAME,
    employee_id: `E2E-${STAMP}-CM3`,
    uploaded_by: "registrar:e2e",
    designation: "Professor",
  }).then((r) => r.body);
  check("seed: three faculty created (chair / member / external expert)",
    Boolean(chair.id && member.id && external.id));

  const scholar = await postJson("/students", {
    name: STUDENT_NAME,
    student_type: "pg",
    roll_number: `E2E-${STAMP}-CS1`,
    uploaded_by: "registrar:e2e",
  }).then((r) => r.body);
  check("seed: student member created", Boolean(scholar.id), scholar.id ?? "");

  const project = await postJson("/research/projects", {
    title: PROJECT_TITLE,
    uploaded_by: "registrar:e2e",
    lifecycle_status: "active",
  }).then((r) => r.body);
  const grant = await postJson("/research/grants", {
    title: GRANT_TITLE,
    grant_number: `E2E-${STAMP}-CG1`,
    uploaded_by: "registrar:e2e",
    amount: 900_000,
    links: { projects: [project.id], funding_agencies: [] },
  }).then((r) => r.body);
  const publication = await postJson("/publications", {
    title: PUB_TITLE,
    publication_type: "journal_article",
    uploaded_by: "registrar:e2e",
    authors: [{ name: "Nandini Rao" }],
    links: { faculty: [chair.id] },
  }).then((r) => r.body);
  check("seed: project + grant + publication link targets created",
    Boolean(project.id && grant.id && publication.id));

  const cpcRes = await postJson("/committees", {
    name: CPC_NAME,
    committee_code: CPC_CODE,
    committee_type: "purchase",
    department: "Administration",
    school: "Central Office",
    description: "Oversees all major purchases and tendering.",
    constitution_date: "2024-01-15",
    expiry_date: "2026-12-31",
    notes: "Quorum: five members.",
    tags: ["governance"],
    uploaded_by: "registrar:e2e",
    status: "active",
    members: [
      { faculty_id: chair.id, role: "chairperson", start_date: "2024-01-15", remarks: "Presiding" },
      { faculty_id: member.id, role: "member" },
      { faculty_id: external.id, role: "external_expert" },
      { faculty_id: scholar.id, role: "student_member" },
    ],
    links: { projects: [project.id], grants: [grant.id], publications: [publication.id] },
  });
  const cpc = cpcRes.body;
  check(
    "seed: host committee created (members + links)",
    cpcRes.status === 201 &&
      cpc.committee_code === CPC_CODE &&
      cpc.members?.length === 4 &&
      cpc.members?.[0]?.role === "chairperson" &&
      cpc.links?.projects?.[0]?.id === project.id,
    cpc.id ?? JSON.stringify(cpcRes.body),
  );

  const dupCode = await postJson("/committees", {
    name: `Duplicate ${STAMP}`,
    committee_code: CPC_CODE,
    uploaded_by: "registrar:e2e",
  });
  check("seed: duplicate committee code rejected (409)", dupCode.status === 409);

  const dupTriple = await postJson("/committees", {
    name: CPC_NAME,
    committee_type: "purchase",
    department: "Administration",
    uploaded_by: "registrar:e2e",
  });
  check("seed: duplicate name+type+department rejected (409)", dupTriple.status === 409);

  const badMember = await postJson("/committees", {
    name: `Broken Committee ${STAMP}`,
    members: [{ faculty_id: project.id, role: "member" }],
    uploaded_by: "registrar:e2e",
  });
  check("seed: non-person member rejected (422)", badMember.status === 422);

  const fin = await postJson("/committees", {
    name: FIN_NAME,
    committee_code: FIN_CODE,
    committee_type: "finance",
    department: "Finance",
    uploaded_by: "registrar:e2e",
    status: "active",
    members: [{ faculty_id: external.id, role: "chairperson" }],
  }).then((r) => r.body);
  check("seed: second committee (finance) for filter variety", Boolean(fin.id));

  const meetingRes = await postJson(`/committees/${cpc.id}/meetings`, {
    title: MEETING_TITLE,
    uploaded_by: "registrar:e2e",
    meeting_number: "7",
    meeting_date: "2026-08-05",
    venue: "Board Room 2",
    mode: "hybrid",
    agenda_items: [
      {
        title: `Procurement of HPC cluster ${STAMP}`,
        priority: "high",
        presenter: CHAIR_NAME,
        status: "pending",
      },
    ],
    minutes: `Draft minutes ${STAMP}: the chair opened with the agenda.`,
    attendance: [
      { object_id: chair.id, status: "present" },
      { object_id: scholar.id, status: "leave" },
      { name: "Prof. External Guest", status: "present" },
    ],
    decisions: [`Approved the L1 quote ${STAMP}`],
  });
  const meeting = meetingRes.body;
  const meetingGet = meeting.id
    ? await getJson(`/committees/meetings/${meeting.id}`).then((r) => r.body)
    : {};
  check(
    "seed: meeting with agenda + attendance + decisions created",
    meetingRes.status === 201 &&
      meeting.meeting_number === "7" &&
      meeting.agenda_items?.length === 1 &&
      meetingGet.attendance?.length === 3 &&
      meetingGet.attendance?.[0]?.name === CHAIR_NAME,
    meeting.id ?? JSON.stringify(meetingRes.body),
  );

  const dupNumber = await postJson(`/committees/${cpc.id}/meetings`, {
    title: `Duplicate ${STAMP}`,
    uploaded_by: "registrar:e2e",
    meeting_number: "7",
  });
  check("seed: duplicate meeting number rejected (409)", dupNumber.status === 409);

  const actionRes = await postJson(`/committees/meetings/${meeting.id}/actions`, {
    title: ACTION_TITLE,
    uploaded_by: "registrar:e2e",
    assigned_to: chair.id,
    due_date: "2026-08-20",
    priority: "high",
    status: "in_progress",
    progress: 40,
  });
  const action = actionRes.body;
  check(
    "seed: action item assigned to the chair (in progress, 40%)",
    actionRes.status === 201 && action.assigned_name === CHAIR_NAME && action.progress === 40,
    action.id ?? JSON.stringify(actionRes.body),
  );

  const badProgress = await postJson(`/committees/meetings/${meeting.id}/actions`, {
    title: `Impossible ${STAMP}`,
    uploaded_by: "registrar:e2e",
    progress: 120,
  });
  check("seed: progress > 100 rejected (422)", badProgress.status === 422);

  const trash = await postJson("/committees", {
    name: TRASH_NAME,
    committee_code: `E2E-${STAMP}-TR1`,
    uploaded_by: "registrar:e2e",
  }).then((r) => r.body);
  const trashMeeting = await postJson(`/committees/${trash.id}/meetings`, {
    title: `Doomed meeting ${STAMP}`,
    uploaded_by: "registrar:e2e",
    meeting_number: "1",
  }).then((r) => r.body);
  check("seed: trash committee + meeting (delete cascade flow)",
    Boolean(trash.id && trashMeeting.id));

  // Attach the agenda supporting document to the seeded meeting (PART 6).
  const form = new FormData();
  form.append("title", DOC_TITLE);
  form.append("document_type", "pdf");
  form.append("uploaded_by", "registrar:e2e");
  form.append("object_id", meeting.id);
  form.append("file", new Blob([`agenda attachment ${STAMP}`], { type: "text/plain" }), "agenda.txt");
  const document_ = await fetch(`${API}/documents`, { method: "POST", body: form }).then((r) =>
    r.json(),
  );
  check("seed: supporting document attached to the seeded meeting", Boolean(document_.id));

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

  try {
    // ---------------------------------------------------- committees hub
    await page.goto(`${BASE}/committees`, { waitUntil: "networkidle0" });
    await page.waitForSelector("h1", { timeout: 30_000 });
    const heading = await page.$eval("h1", (el) => el.textContent?.trim());
    check("committees hub loads", heading?.includes("Committees") ?? false, heading ?? "");
    const navText = await page.$eval("nav", (nav) => nav.innerText);
    check("sidebar exposes the Committees entry", navText.includes("Committees"));

    const hub = await waitForText(page, "UPCOMING MEETINGS", 60_000);
    check(
      "PART 8 dashboard cards render (all six labels)",
      /TOTAL COMMITTEES[\s\S]*ACTIVE COMMITTEES[\s\S]*MEETINGS THIS MONTH[\s\S]*PENDING ACTIONS[\s\S]*COMPLETED ACTIONS[\s\S]*UPCOMING MEETINGS/.test(
        hub.toUpperCase(),
      ),
    );
    const cardsOk =
      Number(await cardValue(page, "TOTAL COMMITTEES")) >= 2 &&
      Number(await cardValue(page, "ACTIVE COMMITTEES")) >= 2 &&
      Number(await cardValue(page, "MEETINGS THIS MONTH")) >= 1 &&
      Number(await cardValue(page, "PENDING ACTIONS")) >= 1 &&
      Number(await cardValue(page, "UPCOMING MEETINGS")) >= 1;
    check("PART 8 card values reflect the seeded graph", cardsOk,
      `total=${await cardValue(page, "TOTAL COMMITTEES")} month=${await cardValue(page, "MEETINGS THIS MONTH")} pending=${await cardValue(page, "PENDING ACTIONS")} upcoming=${await cardValue(page, "UPCOMING MEETINGS")}`);
    check(
      "upcoming meetings panel lists the seeded meeting with its committee",
      hub.includes(MEETING_TITLE) && hub.includes(CPC_NAME),
    );

    // Directory row
    const tableText = await waitForText(page, CPC_NAME, 60_000);
    check(
      "directory table shows the seeded committee (code/type/dept/leadership)",
      tableText.includes(CPC_CODE) &&
        tableText.includes("Purchase") &&
        tableText.includes("Administration"),
    );
    check(
      "directory leadership line shows the chairperson",
      tableText.includes(CHAIR_NAME) && tableText.toLowerCase().includes("chairperson"),
    );

    // PART 9 token search
    await setFieldValue(page, 'input[type="search"]', `nonexistent-${STAMP}`);
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching committees"),
      { timeout: 15_000 },
    );
    check("search: non-matching query shows the empty state", true);
    await setFieldValue(page, 'input[type="search"]', `nandini ${STAMP}`);
    await page.waitForFunction(
      (name) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === name),
      { timeout: 15_000 },
      CPC_NAME,
    );
    check("search: token-AND search finds the committee by member name", true);
    await setFieldValue(page, 'input[type="search"]', "");
    await sleep(600);

    // PART 9 filters
    await page.select('select[aria-label="Filter by committee type"]', "purchase");
    await setFieldValue(page, 'input[aria-label="Filter by department"]', "administration");
    await setFieldValue(page, 'input[aria-label="Filter by chairperson"]', "nandini");
    await page.select('select[aria-label="Filter by status"]', "active");
    await setFieldValue(page, 'input[aria-label="Filter by meeting year"]', "2026");
    await page.waitForFunction(
      (name) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === name),
      { timeout: 15_000 },
      CPC_NAME,
    );
    check("filters: type + department + chairperson + status + meeting year combine", true);
    await page.select('select[aria-label="Filter by committee type"]', "finance");
    await page.waitForFunction(
      (name) =>
        ![...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === name),
      { timeout: 15_000 },
      CPC_NAME,
    );
    check("filters: wrong type excludes the committee (finance row stays)", true);
    await clickButtonWithText(page, "Clear filters");
    await sleep(600);

    // ------------------------------------------------ create via the modal
    await clickButtonWithText(page, "New Committee");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Committee name", MODAL_NAME);
    await typeInField(page, "Committee code", MODAL_CODE);
    await selectInField(page, "Committee type", "research");
    await typeInField(page, "Department", "Chemistry");
    await typeInField(page, "School", "School of Sciences");
    await typeInField(page, "Description", "Departmental research committee.");
    await clickButtonWithText(page, "Add member", { inDialog: true });
    await waitForOption(page, 'select[aria-label="Member 1 person"]', chair.id);
    await page.select('select[aria-label="Member 1 person"]', chair.id);
    await page.select('select[aria-label="Member 1 role"]', "chairperson");
    await setFieldValue(page, 'input[aria-label="Member 1 start date"]', "2025-06-01");
    await clickButtonWithText(page, "Add member", { inDialog: true });
    await waitForOption(page, 'select[aria-label="Member 2 person"]', scholar.id);
    await page.select('select[aria-label="Member 2 person"]', scholar.id);
    await page.select('select[aria-label="Member 2 role"]', "student_member");
    await waitForOption(page, 'select[aria-label="Linked research projects"]', project.id);
    await page.select('select[aria-label="Linked research projects"]', project.id);
    await waitForOption(page, 'select[aria-label="Linked grants"]', grant.id);
    await page.select('select[aria-label="Linked grants"]', grant.id);
    await waitForOption(page, 'select[aria-label="Linked publications"]', publication.id);
    await page.select('select[aria-label="Linked publications"]', publication.id);
    await clickButtonWithText(page, "Create committee");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "created successfully", 15_000);
    check("create: committee registered via the modal (members + links, toast)", true);
    await setFieldValue(page, 'input[type="search"]', `modal ${STAMP}`);
    // The code appears ONLY in the rendered row (the toast has just the name),
    // so waiting for it doubles as the row-render wait after the debounce.
    const modalText = await waitForText(page, MODAL_CODE, 15_000);
    check("create: new committee appears in the directory",
      modalText.includes(MODAL_NAME) && modalText.includes("Chemistry"));
    await setFieldValue(page, 'input[type="search"]', "");
    await sleep(600);

    // duplicate code -> backend 409 surfaces in the modal
    await clickButtonWithText(page, "New Committee");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Committee name", `Duplicate ${STAMP}`);
    await typeInField(page, "Committee code", MODAL_CODE);
    await clickButtonWithText(page, "Create committee");
    await page.waitForSelector('form[role="dialog"] [role="alert"]', { timeout: 15_000 });
    const dupeAlert = await page.$eval(
      'form[role="dialog"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check(
      "duplicate code surfaces the backend 409 in the modal",
      dupeAlert.toLowerCase().includes("code"),
      dupeAlert.slice(0, 90),
    );
    await clickButtonWithText(page, "Cancel", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 10_000,
    });

    // duplicate name+type+department triple -> backend 409 surfaces
    await clickButtonWithText(page, "New Committee");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Committee name", CPC_NAME);
    await selectInField(page, "Committee type", "purchase");
    await typeInField(page, "Department", "Administration");
    await clickButtonWithText(page, "Create committee");
    await page.waitForSelector('form[role="dialog"] [role="alert"]', { timeout: 15_000 });
    const tripleAlert = await page.$eval(
      'form[role="dialog"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check(
      "duplicate name+type+department surfaces the backend 409 in the modal",
      tripleAlert.toLowerCase().includes("already exists") ||
        tripleAlert.toLowerCase().includes("duplicate"),
      tripleAlert.slice(0, 90),
    );
    await clickButtonWithText(page, "Cancel", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 10_000,
    });

    // ------------------------------------------------------ the workspace
    await setFieldValue(page, 'input[type="search"]', `procurement ${STAMP}`);
    await page.waitForFunction(
      (name) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === name),
      { timeout: 15_000 },
      CPC_NAME,
    );
    await clickLinkWithText(page, CPC_NAME);
    const workspace = await waitForText(page, "LINKED RESEARCH & RECORDS", 60_000);
    check(
      "workspace loads (header: name, code, type badge, dept, school)",
      workspace.includes(CPC_NAME) &&
        workspace.includes(CPC_CODE) &&
        workspace.includes("Purchase") &&
        workspace.includes("Administration") &&
        workspace.includes("Central Office"),
    );
    const workspaceUpper = workspace.toUpperCase();
    check(
      "members panel resolves all four with the chairperson first",
      workspaceUpper.includes("MEMBERS (4)") &&
        workspace.indexOf(CHAIR_NAME) < workspace.indexOf(MEMBER_NAME) &&
        workspaceUpper.includes("CHAIRPERSON") &&
        workspaceUpper.includes("EXTERNAL EXPERT") &&
        workspaceUpper.includes("STUDENT MEMBER"),
    );
    check(
      "meetings panel lists the seeded meeting (number + date + mode)",
      workspace.includes(MEETING_TITLE) &&
        workspace.includes("No. 7") &&
        workspace.includes("05 Aug 2026") &&
        workspace.includes("Hybrid"),
    );
    check(
      "PART 7 links panel lists the project, grant and publication",
      workspace.includes(PROJECT_TITLE) &&
        workspace.includes(GRANT_TITLE) &&
        workspace.includes(PUB_TITLE),
    );
    check(
      "audit info renders the Object id + version",
      workspace.includes("obj:committee:") &&
        workspace.includes("Current version") &&
        /v\d+/.test(workspace),
    );

    // meeting create via the workspace modal
    await clickButtonWithText(page, "New meeting");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Meeting title", MODAL_MEETING);
    await typeInField(page, "Meeting number", "1");
    await typeInField(page, "Meeting date", "2026-08-02");
    await typeInField(page, "Venue", "Seminar Hall");
    await selectInField(page, "Mode", "online");
    await clickButtonWithText(page, "Create meeting");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "scheduled successfully", 15_000);
    // "Meetings (2)" appears only after the panel reloads (the toast carries
    // the title too, so waiting on the title alone would race the refresh).
    const meetingsNow = await waitForText(page, "Meetings (2)", 15_000);
    check("meeting: scheduled via the modal and listed (2 meetings)",
      meetingsNow.includes(MODAL_MEETING) && meetingsNow.includes("Online"));

    // duplicate meeting number -> backend 409 in the modal
    await clickButtonWithText(page, "New meeting");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Meeting title", `Duplicate ${STAMP}`);
    await typeInField(page, "Meeting number", "1");
    await clickButtonWithText(page, "Create meeting");
    await page.waitForSelector('form[role="dialog"] [role="alert"]', { timeout: 15_000 });
    const numberAlert = await page.$eval(
      'form[role="dialog"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check(
      "duplicate meeting number surfaces the backend 409 in the modal",
      numberAlert.toLowerCase().includes("number"),
      numberAlert.slice(0, 90),
    );
    await clickButtonWithText(page, "Cancel", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 10_000,
    });

    // ------------------------------------------------------ meeting workspace
    await clickLinkWithText(page, MEETING_TITLE);
    const meetingPage = await waitForText(page, "ACTION TRACKER", 60_000);
    check(
      "meeting workspace loads (title + number + venue + mode badge)",
      meetingPage.includes(MEETING_TITLE) &&
        meetingPage.includes("Meeting no. 7") &&
        meetingPage.includes("Board Room 2") &&
        meetingPage.includes("Hybrid"),
    );
    check(
      "meeting stats line renders (agenda/pending/completed)",
      /AGENDA ITEMS: 1[\s\S]*PENDING ACTIONS: 1[\s\S]*COMPLETED ACTIONS: 0/.test(
        meetingPage.toUpperCase(),
      ),
    );
    // Agenda titles live in INPUT values (not innerText) — assert via the DOM.
    const agenda1Title = await page.$eval(
      'input[aria-label="Agenda item 1 title"]',
      (el) => el.value,
    );
    const agenda1Priority = await page.$eval(
      'select[aria-label="Agenda item 1 priority"]',
      (el) => el.value,
    );
    check(
      "agenda panel shows the seeded item (priority + status badges)",
      agenda1Title === `Procurement of HPC cluster ${STAMP}` &&
        agenda1Priority === "high" &&
        meetingPage.includes("High") &&
        meetingPage.includes("Pending"),
    );
    const guest3 = await page.$eval(
      'input[aria-label="Attendee 3 guest name"]',
      (el) => el.value,
    );
    const attendee2Status = await page.$eval(
      'select[aria-label="Attendee 2 status"]',
      (el) => el.value,
    );
    check(
      "attendance panel shows members resolved + external guest",
      guest3 === "Prof. External Guest" &&
        attendee2Status === "leave" &&
        meetingPage.toUpperCase().includes("ATTENDANCE (3)"),
    );
    const minutesValue = await page.$eval(
      'textarea[aria-label="Meeting minutes"]',
      (el) => el.value,
    );
    const decisionsValue = await page.$eval(
      'textarea[aria-label="Key decisions"]',
      (el) => el.value,
    );
    check(
      "minutes + decisions render",
      minutesValue.includes(`Draft minutes ${STAMP}`) &&
        decisionsValue.includes(`Approved the L1 quote ${STAMP}`),
    );
    check(
      "action tracker shows the seeded action (assignee + progress)",
      meetingPage.includes(ACTION_TITLE) &&
        meetingPage.includes(`Assigned to ${CHAIR_NAME}`) &&
        meetingPage.includes("40%") &&
        meetingPage.includes("In Progress"),
    );

    // PART 4 agenda management: decide the seeded item
    await page.select('select[aria-label="Agenda item 1 status"]', "decided");
    await setFieldValue(
      page,
      'textarea[aria-label="Agenda item 1 decision"]',
      `HPC procurement approved ${STAMP}`,
    );
    await clickButtonWithText(page, "Save agenda");
    const agendaSaved = await waitForText(page, "Meeting saved successfully", 15_000);
    check("agenda: decision saved (status -> decided)", agendaSaved.includes("Decided"));

    // add a second agenda item with the supporting document (PART 6)
    await clickButtonWithText(page, "Add item");
    await setFieldValue(
      page,
      'input[aria-label="Agenda item 2 title"]',
      `Budget ratification ${STAMP}`,
    );
    await page.select('select[aria-label="Agenda item 2 priority"]', "medium");
    await setFieldValue(page, 'input[aria-label="Agenda item 2 presenter"]', MEMBER_NAME);
    await waitForOption(
      page,
      'select[aria-label="Agenda item 2 supporting documents"]',
      document_.id,
    );
    await page.select(
      'select[aria-label="Agenda item 2 supporting documents"]',
      document_.id,
    );
    await clickButtonWithText(page, "Save agenda");
    await waitForText(page, "Meeting saved successfully", 20_000);
    // The toast is identical to save #1's and the "1 supporting document(s)"
    // line is local editor state, so confirm the SECOND save landed via the
    // API before reading the re-rendered snapshot.
    const agendaTwoApi = await waitApi(
      `/committees/meetings/${meeting.id}`,
      (m) =>
        m.stats?.agenda_items === 2 &&
        (m.agenda_items ?? []).some(
          (item) =>
            (item.title ?? "") === `Budget ratification ${STAMP}` &&
            (item.document_ids ?? []).includes(document_.id) &&
            (item.supporting_documents ?? []).some((doc) => doc.id === document_.id),
        ),
    );
    const agendaTwo = await waitForText(page, "AGENDA ITEMS: 2", 20_000);
    const agenda2Title = await page.$eval(
      'input[aria-label="Agenda item 2 title"]',
      (el) => el.value,
    );
    const agenda2Docs = await page.$eval(
      'select[aria-label="Agenda item 2 supporting documents"]',
      (el) => [...el.selectedOptions].map((option) => option.value),
    );
    check(
      "agenda: second item with a supporting document saved",
      agenda2Title === `Budget ratification ${STAMP}` &&
        agenda2Docs.includes(document_.id) &&
        agendaTwoApi.stats?.agenda_items === 2 &&
        agendaTwo.toUpperCase().includes("1 SUPPORTING DOCUMENT(S)"),
      `title=${agenda2Title} docs=${agenda2Docs} want=${document_.id}`,
    );

    // attendance update: student now present + add an external guest row
    await page.select('select[aria-label="Attendee 2 status"]', "present");
    await clickButtonWithText(page, "Add attendee");
    await setFieldValue(
      page,
      'input[aria-label="Attendee 4 guest name"]',
      `Dr. Guest ${STAMP}`,
    );
    await page.select('select[aria-label="Attendee 4 status"]', "present");
    await clickButtonWithText(page, "Save attendance");
    await waitForText(page, "Meeting saved successfully", 20_000);
    // Confirm the attendance save landed (the toast can be the previous
    // panel save's lingering one) before reading the re-rendered rows.
    const attendanceApi = await waitApi(
      `/committees/meetings/${meeting.id}`,
      (m) =>
        (m.attendance ?? []).length === 4 &&
        m.attendance.some(
          (row) => (row.name ?? "") === `Dr. Guest ${STAMP}` && row.status === "present",
        ) &&
        m.attendance.some(
          (row) => row.object_id === scholar.id && row.status === "present",
        ),
    );
    const attendanceSaved = await waitForText(page, "ATTENDANCE (4)", 20_000);
    const guest4 = await page.$eval(
      'input[aria-label="Attendee 4 guest name"]',
      (el) => el.value,
    );
    const attendee2After = await page.$eval(
      'select[aria-label="Attendee 2 status"]',
      (el) => el.value,
    );
    check("attendance: four rows saved (guest added, student marked present)",
      guest4 === `Dr. Guest ${STAMP}` &&
        attendee2After === "present" &&
        attendanceApi.attendance?.length === 4 &&
        attendanceSaved.toUpperCase().includes("ATTENDANCE (4)"));

    // minutes & decisions
    await setFieldValue(
      page,
      'textarea[aria-label="Meeting minutes"]',
      `Signed minutes ${STAMP}: quorum present.`,
    );
    await setFieldValue(
      page,
      'textarea[aria-label="Key decisions"]',
      `Approved the L1 quote ${STAMP}\nRatified the budget head ${STAMP}`,
    );
    await clickButtonWithText(page, "Save minutes");
    await waitForText(page, "Meeting saved successfully", 20_000);
    // Again the toast may predate this save — poll the API until the signed
    // minutes + the second decision line are persisted.
    const minutesApi = await waitApi(
      `/committees/meetings/${meeting.id}`,
      (m) =>
        (m.minutes ?? "").includes(`Signed minutes ${STAMP}`) &&
        (m.decisions ?? []).some((line) =>
          line.includes(`Ratified the budget head ${STAMP}`),
        ),
    );
    const minutesAfter = await page.$eval(
      'textarea[aria-label="Meeting minutes"]',
      (el) => el.value,
    );
    const decisionsAfter = await page.$eval(
      'textarea[aria-label="Key decisions"]',
      (el) => el.value,
    );
    check("minutes & decisions saved (both lines render)",
      minutesAfter.includes(`Signed minutes ${STAMP}`) &&
        decisionsAfter.includes(`Ratified the budget head ${STAMP}`) &&
        (minutesApi.decisions ?? []).some((line) =>
          line.includes(`Ratified the budget head ${STAMP}`),
        ));

    // PART 5 action tracker: add, edit progress, mark done, delete
    await clickButtonWithText(page, "Add action");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Action title", FOLLOWUP_TITLE);
    await selectInField(page, "Assigned to", chair.id);
    await typeInField(page, "Due date", "2026-08-25");
    await selectInField(page, "Priority", "medium");
    await typeInField(page, "Progress (%)", "10");
    await clickButtonWithText(page, "Create action");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    const actionAdded = await waitForText(page, FOLLOWUP_TITLE, 15_000);
    check("action: added via the modal (10% progress renders)",
      actionAdded.includes("10%") && actionAdded.toUpperCase().includes("ACTION TRACKER (2)"));

    const editLabel = `Edit "${FOLLOWUP_TITLE}"`;
    await page.evaluate((label) => {
      const button = [...document.querySelectorAll("button")].find(
        (btn) => btn.getAttribute("aria-label") === label,
      );
      button?.click();
    }, editLabel);
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Progress (%)", "60");
    await clickButtonWithText(page, "Save changes");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "60%", 15_000);
    check("action: progress edited to 60%", true);

    const doneLabel = `Mark "${ACTION_TITLE}" done`;
    await page.evaluate((label) => {
      const button = [...document.querySelectorAll("button")].find(
        (btn) => btn.getAttribute("aria-label") === label,
      );
      button?.click();
    }, doneLabel);
    const actionDone = await waitForText(page, "COMPLETED ACTIONS: 1", 20_000);
    check(
      "action: seeded item marked done (100% + completed stats)",
      actionDone.includes("100%") && actionDone.includes("Done"),
    );

    const deleteLabel = `Delete "${FOLLOWUP_TITLE}"`;
    await page.evaluate((label) => {
      const button = [...document.querySelectorAll("button")].find(
        (btn) => btn.getAttribute("aria-label") === label,
      );
      button?.click();
    }, deleteLabel);
    const actionDeleted = await waitForText(page, "PENDING ACTIONS: 0", 20_000);
    check("action: follow-up deleted from the tracker",
      !actionDeleted.includes(FOLLOWUP_TITLE) &&
        actionDeleted.toUpperCase().includes("ACTION TRACKER (1)"));

    // back to the committee: meetings/stats reconcile
    await clickButtonWithText(page, "Back to committee");
    await waitForText(page, MODAL_MEETING, 30_000); // panel reloaded after navigation
    await clickLinkWithText(page, MODAL_MEETING);
    await waitForText(page, "Meeting no. 1", 60_000);
    check("breadcrumb navigates into the modal-created meeting", true);

    // delete the modal meeting -> flash on the committee workspace
    await clickButtonWithText(page, "Delete");
    await page.waitForSelector('[role="alertdialog"], [role="dialog"]', { timeout: 10_000 });
    await clickButtonWithText(page, "Delete", { inDialog: true });
    await waitForText(page, "was deleted", 30_000);
    check("delete meeting: confirm dialog redirects to the committee with a flash",
      page.url().includes("/committees/"));
    const committeeAgain = await waitForText(page, "MEETINGS (1)", 30_000);
    // The flash toast names the just-deleted meeting, so the "meeting is
    // gone" assertion is scoped to the meetings panel section (the toast
    // auto-dismisses after 4s and is not part of the reconciled record).
    const meetingsPanelText = await page.evaluate(() => {
      const section = [...document.querySelectorAll("section")].find((el) =>
        (el.innerText ?? "").toUpperCase().includes("MEETINGS (1)"),
      );
      return (section?.innerText ?? "").toUpperCase();
    });
    check(
      "committee reconciles after meeting delete (stats: 1 completed action)",
      committeeAgain.toUpperCase().includes("COMPLETED ACTIONS") &&
        meetingsPanelText.length > 0 &&
        !meetingsPanelText.includes(MODAL_MEETING.toUpperCase()),
    );

    // faculty lens: the chair picks up the committee memberships
    await page.goto(`${BASE}/faculty/${encodeURIComponent(chair.id)}`, {
      waitUntil: "networkidle0",
    });
    const facultyLens = await waitForText(page, "STUDENTS SUPERVISED", 60_000);
    check(
      "faculty lens: committees stat reflects committee-module memberships",
      facultyLens.includes(CPC_NAME) && facultyLens.includes(MODAL_NAME),
    );
    const chairCommittees = await cardValue(page, "COMMITTEES");
    check("faculty lens: COMMITTEES card counts both memberships", chairCommittees === "2",
      `value=${chairCommittees}`);

    // ------------------------------------------- dashboard after the flows
    await page.goto(`${BASE}/committees`, { waitUntil: "networkidle0" });
    await waitForText(page, "TOTAL COMMITTEES", 60_000);
    const completedNow = Number(await cardValue(page, "COMPLETED ACTIONS"));
    check("dashboard: completed actions card advanced", completedNow >= 1,
      `value=${completedNow}`);

    // ------------------------------------------------------------- delete
    await setFieldValue(page, 'input[type="search"]', `trash ${STAMP}`);
    await page.waitForFunction(
      (name) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === name),
      { timeout: 15_000 },
      TRASH_NAME,
    );
    await clickLinkWithText(page, TRASH_NAME);
    await waitForText(page, "Audit Information", 30_000); // workspace-only marker
    await clickButtonWithText(page, "Delete");
    await page.waitForSelector('[role="alertdialog"], [role="dialog"]', { timeout: 10_000 });
    await clickButtonWithText(page, "Delete", { inDialog: true });
    await waitForText(page, "was deleted", 30_000);
    check("delete: confirm dialog redirects with a flash toast",
      page.url().endsWith("/committees"));
    await setFieldValue(page, 'input[type="search"]', `trash ${STAMP}`);
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching committees"),
      { timeout: 15_000 },
    );
    check("delete: the committee is gone from the directory", true);
    const orphan = await getJson(`/committees/meetings/${trashMeeting.id}`);
    check("delete cascade: the meeting under the deleted committee 404s",
      orphan.status === 404, String(orphan.status));

    // --------------------------------------------------------- 404 state
    await page.goto(`${BASE}/committees/${encodeURIComponent("obj:committee:MISSING")}`, {
      waitUntil: "networkidle0",
    });
    await waitForText(page, "Committee not found", 30_000);
    check("404 state renders for a missing committee id", true);

    // --------------------------------------------------------- cleanliness
    const hostileApi = failedResponses.filter((line) => {
      if (!line.includes("/api/v1/")) return false;
      // Intentional checks above: duplicate code/triple 409s on create, the
      // duplicate meeting-number 409 and the progress-120 422 are on purpose.
      if (line.startsWith("409 POST") && line.endsWith("/api/v1/committees")) return false;
      if (line.startsWith("409 POST") && line.includes("/api/v1/committees/") && line.endsWith("/meetings")) return false;
      if (line.startsWith("422 POST") && line.includes("/actions")) return false;
      // The 404-state check above opens a deliberately missing id.
      if (line.startsWith("404 GET") && line.includes("/api/v1/committees/obj:committee:MISSING")) {
        return false;
      }
      return true;
    });
    check("no failing API requests (>=400)", hostileApi.length === 0, hostileApi[0] ?? "");
    const hostile = consoleErrors.filter(
      (line) =>
        !line.includes("favicon") &&
        !line.includes("404 (Not Found)") && // /favicon.ico — no favicon ships yet
        // The intentional 409/422 checks log as console errors in chromium.
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

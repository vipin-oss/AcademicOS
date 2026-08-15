/**
 * Research Projects & Grants module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   research dashboard (PART 10 cards + upcoming deadlines) -> projects
 *   registry with PART 9 filters (q / PI / agency / lifecycle / year /
 *   department) -> register + duplicate-code 409 in the modal -> project
 *   workspace (header, PART 7 budget card with grants-released reactivity,
 *   team panel, grants panel, PART 8 timeline: milestone add / mark done /
 *   delete + progress update completion bar, publications / documents /
 *   students lenses) -> lifecycle advance via edit -> grant workspace
 *   (PART 7 budget header, installments + budget-guard 422, expenditure,
 *   funded-projects links) -> grants registry -> agencies registry
 *   (create / edit / duplicate-name 409 / delete) -> dashboard reactivity.
 *
 * Usage:
 *   node tests/research-e2e.mjs            # http://127.0.0.1:3000
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
const AGENCY_NAME = `SERB E2E ${STAMP}`;
const FACULTY_NAME = `Prof E2E ${STAMP}`;
const STUDENT_NAME = `Asha Verma ${STAMP}`;
const PROJECT_TITLE = `E2E Quantum Dots ${STAMP}`;
const PROJECT_CODE = `E2E-${STAMP}-P01`;
const PROJECT_TITLE_UI = `E2E Solar Cells ${STAMP}`;
const PROJECT_CODE_UI = `E2E-${STAMP}-P02`;
const MILESTONE_TITLE = `Mid-term review E2E ${STAMP}`;
const MILESTONE_TITLE_UI = `Final report E2E ${STAMP}`;
const GRANT_TITLE = `SERB Core Research Grant ${STAMP}`;
const GRANT_NUMBER = `E2E-${STAMP}-G01`;
const GRANT_TITLE_UI = `Equipment Grant ${STAMP}`;
const GRANT_NUMBER_UI = `E2E-${STAMP}-G02`;
const PUB_TITLE = `E2E Quantum Dots Study ${STAMP}`;
const DOC_TITLE = `Sanction Letter E2E ${STAMP}`;
const TRASH_AGENCY = `E2E Trash Agency ${STAMP}`;

const postJson = (path, body, method = "POST") =>
  fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

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

async function main() {
  // ---------------------------------------------------- seed via the real API
  const agencyRes = await postJson("/research/agencies", {
    name: AGENCY_NAME,
    uploaded_by: "faculty:e2e",
    scheme: "Core Research Grant",
    website: "https://serb.gov.in",
    contact_email: "crg@serb.gov.in",
  });
  const agency = agencyRes.body;
  check("seed: funding agency created", Boolean(agency.id), agency.id ?? JSON.stringify(agencyRes.body));

  const dupAgency = await postJson("/research/agencies", {
    name: AGENCY_NAME,
    uploaded_by: "faculty:e2e",
  });
  check("seed: duplicate agency name rejected (409)", dupAgency.status === 409);

  const faculty = await postJson("/objects", {
    object_type: "faculty",
    title: FACULTY_NAME,
    created_by: "faculty:e2e",
  }).then((r) => r.body);
  const student = await postJson("/students", {
    name: STUDENT_NAME,
    uploaded_by: "faculty:e2e",
    student_type: "phd",
    roll_number: `E2E-${STAMP}-201`,
    department: "Physics",
  }).then((r) => r.body);
  check("seed: faculty (PI) + student (team) created", Boolean(faculty.id && student.id));

  const projectRes = await postJson("/research/projects", {
    title: PROJECT_TITLE,
    uploaded_by: "faculty:e2e",
    lifecycle_status: "funded",
    project_code: PROJECT_CODE,
    department: "Physics",
    grant_number: GRANT_NUMBER,
    start_date: "2026-04-01",
    end_date: "2029-03-31",
    duration: "36 months",
    budget_approved: 4_500_000,
    budget_utilized: 0,
    objectives: "Synthesise perovskite quantum dots.",
    keywords: ["quantum", "perovskite"],
    priority: "high",
    links: { agencies: [agency.id], committees: [] },
    team: {
      principal_investigators: [faculty.id],
      co_investigators: [],
      team_members: [student.id],
    },
  });
  const project = projectRes.body;
  check(
    "seed: project created (links + team + budget)",
    Boolean(project.id) && project.budget?.approved === 4_500_000,
    project.id ?? JSON.stringify(projectRes.body),
  );

  const dupProject = await postJson("/research/projects", {
    title: `Duplicate ${STAMP}`,
    uploaded_by: "faculty:e2e",
    project_code: PROJECT_CODE,
  });
  check("seed: duplicate project code rejected (409)", dupProject.status === 409);

  const milestone = await postJson(`/research/projects/${project.id}/milestones`, {
    title: MILESTONE_TITLE,
    date: "2026-12-31",
    uploaded_by: "faculty:e2e",
  }).then((r) => r.body);
  check("seed: pending milestone added (dashboard deadline)", Boolean(milestone.id));

  const grantRes = await postJson("/research/grants", {
    title: GRANT_TITLE,
    grant_number: GRANT_NUMBER,
    uploaded_by: "faculty:e2e",
    amount: 3_000_000,
    release_schedule: "annual",
    links: { projects: [project.id], funding_agencies: [agency.id] },
  });
  const grant = grantRes.body;
  check(
    "seed: grant created (funds project, funded by agency)",
    Boolean(grant.id) && grant.budget?.approved === 3_000_000,
    grant.id ?? JSON.stringify(grantRes.body),
  );

  const dupGrant = await postJson("/research/grants", {
    title: `Duplicate ${STAMP}`,
    grant_number: GRANT_NUMBER,
    uploaded_by: "faculty:e2e",
  });
  check("seed: duplicate grant number rejected (409)", dupGrant.status === 409);

  const installment = await postJson(`/research/grants/${grant.id}/installments`, {
    installment_no: 1,
    date: "2026-04-15",
    amount: 1_500_000,
    status: "released",
    notes: "First release",
    uploaded_by: "faculty:e2e",
  }).then((r) => r.body);
  check("seed: released installment recorded (₹15,00,000)", Boolean(installment.id));

  const overRelease = await postJson(`/research/grants/${grant.id}/installments`, {
    installment_no: 9,
    date: "2026-05-01",
    amount: 2_000_000,
    status: "released",
    uploaded_by: "faculty:e2e",
  });
  check("seed: budget guard — over-release rejected (422)", overRelease.status === 422);

  // Publications + documents lenses for the project workspace.
  const publication = await postJson("/publications", {
    title: PUB_TITLE,
    publication_type: "journal_article",
    uploaded_by: "faculty:e2e",
    authors: [{ name: FACULTY_NAME }],
    keywords: ["quantum"],
    links: { projects: [project.id] },
  }).then((r) => r.body);
  check("seed: publication linked to the project", Boolean(publication.id), publication.id ?? "");

  const form = new FormData();
  form.append("title", DOC_TITLE);
  form.append("document_type", "pdf");
  form.append("uploaded_by", "faculty:e2e");
  form.append("object_id", project.id);
  form.append("file", new Blob([`sanction letter ${STAMP}`], { type: "text/plain" }), "sanction.txt");
  const document_ = await fetch(`${API}/documents`, { method: "POST", body: form }).then((r) =>
    r.json(),
  );
  check("seed: sanction-letter document attached to the project", Boolean(document_.id));

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
    // --------------------------------------------------- research dashboard
    await page.goto(`${BASE}/research`, { waitUntil: "networkidle0" });
    await page.waitForSelector("h1", { timeout: 30_000 });
    const heading = await page.$eval("h1", (el) => el.textContent?.trim());
    check(
      "research hub loads",
      heading?.includes("Research") ?? false,
      heading ?? "",
    );
    const navText = await page.$eval("nav", (nav) => nav.innerText);
    check("sidebar exposes the Research entry", navText.includes("Research"));

    // PART 10 cards land (numbers), then the upcoming-deadlines panel.
    const dashText = await waitForText(page, "BUDGET APPROVED", 60_000);
    check(
      "dashboard cards render (PART 10)",
      /TOTAL PROJECTS[\s\S]*ACTIVE PROJECTS[\s\S]*COMPLETED[\s\S]*TOTAL GRANTS/.test(
        dashText.toUpperCase(),
      ),
    );
    const deadlineText = await waitForText(page, MILESTONE_TITLE, 30_000);
    check(
      "upcoming deadlines panel shows the seeded milestone + project",
      deadlineText.includes(PROJECT_TITLE),
    );

    // ----------------------------------------------------- projects registry
    const registryText = await waitForText(page, PROJECT_TITLE, 30_000);
    check(
      "projects table shows code + agency line + lifecycle badge",
      registryText.includes(PROJECT_CODE) &&
        registryText.includes(AGENCY_NAME) &&
        registryText.includes("Funded"),
    );
    check(
      "+ part 9: year + department render in the row",
      registryText.includes("Physics") && registryText.includes("2026"),
    );

    // PART 9: token search
    await setFieldValue(page, 'input[type="search"]', `nonexistent-${STAMP}`);
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching projects"),
      { timeout: 15_000 },
    );
    check("search: non-matching query shows the empty state", true);
    await setFieldValue(page, 'input[type="search"]', `quantum dots ${STAMP}`);
    await page.waitForFunction(
      (title) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === title),
      { timeout: 15_000 },
      PROJECT_TITLE,
    );
    check("search: token search finds the project (server-side q)", true);
    await setFieldValue(page, 'input[type="search"]', "");
    await sleep(600);

    // PART 9: PI filter (team-name reverse scan)
    await setFieldValue(page, 'input[aria-label="Filter by PI"]', FACULTY_NAME);
    await page.waitForFunction(
      (title) => {
        const rows = [...document.querySelectorAll("table a")];
        return rows.length === 1 && rows[0].textContent?.trim() === title;
      },
      { timeout: 15_000 },
      PROJECT_TITLE,
    );
    check("PART 9 filter: PI name narrows to exactly the project", true);

    // PART 9: agency + lifecycle + year + department filters
    await waitForOption(page, 'select[aria-label="Filter by agency"]', AGENCY_NAME);
    await page.select('select[aria-label="Filter by agency"]', AGENCY_NAME);
    await page.select('select[aria-label="Filter by lifecycle status"]', "funded");
    await setFieldValue(page, 'input[aria-label="Filter by year"]', "2026");
    await setFieldValue(page, 'input[aria-label="Filter by department"]', "Physics");
    await page.waitForFunction(
      (title) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === title),
      { timeout: 15_000 },
      PROJECT_TITLE,
    );
    check("PART 9 filters: agency + lifecycle + year + department combine", true);
    await page.select('select[aria-label="Filter by lifecycle status"]', "completed");
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching projects"),
      { timeout: 15_000 },
    );
    check("PART 9 filters: wrong lifecycle excludes the project", true);
    await clickButtonWithText(page, "Clear filters");
    await sleep(600);

    // ------------------------------------------- register project via modal
    await clickButtonWithText(page, "New Project");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Project title", PROJECT_TITLE_UI);
    await typeInField(page, "Project code", PROJECT_CODE_UI);
    await typeInField(page, "Department", "Chemistry");
    await page.select(
      'form[role="dialog"] select[aria-label="Lifecycle status"]',
      "approved",
    );
    await waitForOption(
      page,
      'form[role="dialog"] select[aria-label="Linked funding agencies"]',
      agency.id,
    );
    await page.select(
      'form[role="dialog"] select[aria-label="Linked funding agencies"]',
      agency.id,
    );
    await clickButtonWithText(page, "Register project");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "registered successfully", 15_000);
    check("create: project registered via the modal (toast)", true);
    await setFieldValue(page, 'input[type="search"]', `solar cells ${STAMP}`);
    const solarText = await waitForText(page, PROJECT_TITLE_UI, 15_000);
    check(
      "create: new project appears with the picked agency on its row",
      solarText.includes(AGENCY_NAME),
    );
    await setFieldValue(page, 'input[type="search"]', "");
    await sleep(600);

    // duplicate code -> backend 409 surfaces in the modal
    await clickButtonWithText(page, "New Project");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Project title", `Duplicate ${STAMP}`);
    await typeInField(page, "Project code", PROJECT_CODE);
    await clickButtonWithText(page, "Register project");
    await page.waitForSelector('form[role="dialog"] [role="alert"]', { timeout: 15_000 });
    const dupeAlert = await page.$eval(
      'form[role="dialog"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check(
      "duplicate code surfaces the backend 409 in the modal",
      dupeAlert.toLowerCase().includes("duplicate"),
      dupeAlert.slice(0, 90),
    );
    await clickButtonWithText(page, "Cancel", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 10_000,
    });

    // ------------------------------------------------- project workspace
    await page.evaluate((title) => {
      const link = [...document.querySelectorAll("table a")].find(
        (a) => a.textContent?.trim() === title,
      );
      link?.click();
    }, PROJECT_TITLE);
    // NOTE: the project code ALSO renders on the registry row — anchor the
    // navigation on the URL, then on workspace-only markers (the grants panel
    // fetches asynchronously; its title is the last piece to land).
    await page.waitForFunction(
      (code) =>
        location.pathname.startsWith("/research/projects/") &&
        document.body.innerText.includes(code),
      { timeout: 30_000 },
      PROJECT_CODE,
    );
    const workspaceText = await waitForText(page, GRANT_TITLE, 30_000);
    check("workspace opens from the registry row (click-through)", true);
    check(
      "workspace header: title + lifecycle badge + grant ref + dates",
      workspaceText.includes(PROJECT_TITLE) &&
        workspaceText.includes("Funded") &&
        workspaceText.includes(GRANT_NUMBER) &&
        workspaceText.includes("36 months"),
    );
    check(
      "PART 7 budget card: approved + grants released (grant reactivity)",
      workspaceText.includes("45,00,000") && workspaceText.includes("15,00,000"),
    );
    check(
      "team panel: PI + team member (typed person edges)",
      workspaceText.includes(FACULTY_NAME) && workspaceText.includes(STUDENT_NAME),
    );
    check(
      "grants panel lists the funding grant with amounts",
      workspaceText.includes(GRANT_TITLE) && workspaceText.includes("30,00,000"),
    );
    check("timeline shows the seeded milestone", workspaceText.includes(MILESTONE_TITLE));

    // object lenses (publications / documents / students)
    const lensText = await waitForText(page, PUB_TITLE, 30_000);
    check("object lens: project page shows the related publication", true);
    check(
      "object lenses: documents + students panes render the linked records",
      lensText.includes(DOC_TITLE) && lensText.includes(STUDENT_NAME),
    );

    // lifecycle advance via the edit modal
    await clickButtonWithText(page, "Edit");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await page.select(
      'form[role="dialog"] select[aria-label="Lifecycle status"]',
      "active",
    );
    await clickButtonWithText(page, "Save changes");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "updated successfully", 15_000);
    const afterEdit = await page.evaluate(() => document.body.innerText);
    // The universal status badge ALSO reads "Active" — the signal that the
    // LIFECYCLE badge moved is that "Funded" no longer appears on the page.
    check(
      "lifecycle advance: funded -> active badge after edit",
      afterEdit.includes("Active") && !afterEdit.includes("Funded"),
    );

    // PART 8 timeline: add milestone, log progress update, mark done, delete
    await clickButtonWithText(page, "Add milestone");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Milestone title", MILESTONE_TITLE_UI);
    await typeInField(page, "Due date", "2028-12-31");
    await clickButtonWithText(page, "Add milestone", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, MILESTONE_TITLE_UI, 15_000);
    check("timeline: milestone added via the modal", true);

    await clickButtonWithText(page, "Log update");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Date", "2026-08-01");
    await typeInField(page, "Completion (%)", "40");
    await typeInField(page, "Remark", "Data collection finished; analysis started.");
    await clickButtonWithText(page, "Log update", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    const progressText = await waitForText(page, "40% complete", 15_000);
    check(
      "timeline: progress update moves the completion bar + feed",
      progressText.includes("Data collection finished") && progressText.includes("40%"),
    );

    await page.evaluate((title) => {
      const button = [...document.querySelectorAll("button")].find(
        (btn) => btn.getAttribute("aria-label") === `Mark ${title} done`,
      );
      button?.click();
    }, MILESTONE_TITLE);
    await page.waitForFunction(
      (title) => {
        const items = [...document.querySelectorAll("li")];
        const row = items.find((li) => li.innerText.includes(title));
        return row ? row.innerText.includes("Done") : false;
      },
      { timeout: 15_000 },
      MILESTONE_TITLE,
    );
    check("timeline: milestone marked done (status badge flips)", true);

    await page.evaluate((title) => {
      const button = [...document.querySelectorAll("button")].find(
        (btn) => btn.getAttribute("aria-label") === `Delete ${title}`,
      );
      button?.click();
    }, MILESTONE_TITLE_UI);
    await page.waitForFunction(
      (title) => !document.body.innerText.includes(title),
      { timeout: 15_000 },
      MILESTONE_TITLE_UI,
    );
    check("timeline: milestone deleted", true);

    // register a second grant FROM the workspace (project pre-selected)
    await clickButtonWithText(page, "New grant");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    // Picker options load asynchronously — the pre-selected value binds once
    // the project <option> element exists.
    await page.waitForFunction(
      (projectId) => {
        const select = document.querySelector(
          'form[role="dialog"] select[aria-label="Linked projects"]',
        );
        return select
          ? [...select.selectedOptions].some((option) => option.value === projectId)
          : false;
      },
      { timeout: 15_000 },
      project.id,
    );
    check("workspace new grant: funded project pre-selected", true);
    await typeInField(page, "Grant title", GRANT_TITLE_UI);
    await typeInField(page, "Grant number", GRANT_NUMBER_UI);
    await typeInField(page, "Sanctioned amount", "500000");
    await clickButtonWithText(page, "Register grant");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "registered successfully", 15_000);
    const panelText = await waitForText(page, GRANT_TITLE_UI, 15_000);
    check(
      "grants panel refreshes with the new grant (budget card intact)",
      panelText.includes("15,00,000"),
    );

    // ----------------------------------------------------- grant workspace
    await page.goto(`${BASE}/research/grants/${encodeURIComponent(grant.id)}`, {
      waitUntil: "networkidle0",
    });
    const grantText = await waitForText(page, GRANT_NUMBER, 30_000);
    check("grant workspace opens (breadcrumbs + number)", true);
    check(
      "PART 7 header: sanctioned / released / utilized / remaining",
      grantText.includes("30,00,000") && grantText.includes("15,00,000"),
    );
    check(
      "grant identity: agency + release schedule + funded project",
      grantText.includes(AGENCY_NAME) &&
        grantText.includes("annual") &&
        grantText.includes(PROJECT_TITLE),
    );
    check(
      "installments panel lists the released tranche",
      grantText.includes("Installment #1") && grantText.includes("Released"),
    );

    // budget guard via the modal (over-release) -> 422 alert
    await clickButtonWithText(page, "Add installment");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Installment no.", "2");
    await typeInField(page, "Release date", "2026-08-01");
    await typeInField(page, "Amount (₹)", "2000000");
    await clickButtonWithText(page, "Add installment", { inDialog: true });
    await page.waitForSelector('form[role="dialog"] [role="alert"]', { timeout: 15_000 });
    const guardAlert = await page.$eval(
      'form[role="dialog"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check(
      "PART 7 guard: over-release 422 surfaces in the modal",
      guardAlert.toLowerCase().includes("exceed"),
      guardAlert.slice(0, 90),
    );
    await clickButtonWithText(page, "Cancel", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 10_000,
    });

    // a valid scheduled installment + an expenditure
    await clickButtonWithText(page, "Add installment");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Installment no.", "2");
    await typeInField(page, "Release date", "2027-04-01");
    await typeInField(page, "Amount (₹)", "1000000");
    await page.select(
      'form[role="dialog"] select[aria-label="Installment status"]',
      "scheduled",
    );
    await clickButtonWithText(page, "Add installment", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    const instText = await waitForText(page, "Installment #2", 15_000);
    check(
      "scheduled installment recorded (does not inflate released)",
      instText.includes("Scheduled") && !instText.includes("25,00,000"),
    );

    await clickButtonWithText(page, "Record expenditure");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Date", "2026-07-15");
    await typeInField(page, "Budget head", "Equipment");
    await typeInField(page, "Amount (₹)", "250000");
    await typeInField(page, "Reference", `VCH-${STAMP}`);
    await clickButtonWithText(page, "Record expenditure", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    const expText = await waitForText(page, "Equipment", 15_000);
    check(
      "expenditure recorded: utilized ₹2,50,000 / remaining ₹27,50,000",
      expText.includes("2,50,000") && expText.includes("27,50,000"),
    );

    // delete the expenditure + scheduled installment (panels stay consistent)
    await page.evaluate(() => {
      const button = [...document.querySelectorAll("button")].find((btn) =>
        btn.getAttribute("aria-label")?.startsWith("Delete expenditure"),
      );
      button?.click();
    });
    await page.waitForFunction(() => !document.body.innerText.includes("Equipment"), {
      timeout: 15_000,
    });
    check("expenditure deleted (utilized back to zero)", true);
    await page.evaluate(() => {
      const button = [...document.querySelectorAll("button")].find((btn) =>
        btn.getAttribute("aria-label")?.startsWith("Delete installment 2"),
      );
      button?.click();
    });
    await page.waitForFunction(() => !document.body.innerText.includes("Installment #2"), {
      timeout: 15_000,
    });
    check("scheduled installment deleted", true);

    // ------------------------------------------------------ grants registry
    await page.goto(`${BASE}/research/grants`, { waitUntil: "networkidle0" });
    await page.waitForSelector("h1", { timeout: 30_000 });
    const grantsHeading = await page.$eval("h1", (el) => el.textContent?.trim());
    check("grants registry loads", grantsHeading === "Grants", grantsHeading ?? "");
    const grantsText = await waitForText(page, GRANT_NUMBER, 30_000);
    check(
      "grant row shows agency + funded project + budget cells",
      grantsText.includes(AGENCY_NAME) && grantsText.includes(PROJECT_TITLE),
    );
    await setFieldValue(page, 'input[type="search"]', GRANT_NUMBER);
    await page.waitForFunction(
      (title) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === title),
      { timeout: 15_000 },
      GRANT_TITLE,
    );
    check("grants search by number (server-side q)", true);

    // ---------------------------------------------------- agencies registry
    await page.goto(`${BASE}/research/agencies`, { waitUntil: "networkidle0" });
    await page.waitForSelector("h1", { timeout: 30_000 });
    const agenciesHeading = await page.$eval("h1", (el) => el.textContent?.trim());
    check(
      "agencies registry loads",
      agenciesHeading === "Funding Agencies",
      agenciesHeading ?? "",
    );
    const agenciesText = await waitForText(page, AGENCY_NAME, 30_000);
    check(
      "agency row shows scheme + website link",
      agenciesText.includes("Core Research Grant"),
    );

    // create + duplicate-name 409 + edit + delete, all through the UI
    await clickButtonWithText(page, "New Agency");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Agency name", TRASH_AGENCY);
    await typeInField(page, "Scheme", "Seed Scheme");
    await clickButtonWithText(page, "Register agency");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "registered successfully", 15_000);
    check("agency registered via the modal", true);

    await clickButtonWithText(page, "New Agency");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Agency name", TRASH_AGENCY);
    await clickButtonWithText(page, "Register agency");
    await page.waitForSelector('form[role="dialog"] [role="alert"]', { timeout: 15_000 });
    const dupeAgencyAlert = await page.$eval(
      'form[role="dialog"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check(
      "duplicate agency name surfaces the backend 409 in the modal",
      dupeAgencyAlert.toLowerCase().includes("duplicate"),
      dupeAgencyAlert.slice(0, 90),
    );
    await clickButtonWithText(page, "Cancel", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 10_000,
    });

    await page.evaluate((name) => {
      const button = [...document.querySelectorAll("button")].find(
        (btn) => btn.getAttribute("aria-label") === `Edit ${name}`,
      );
      button?.click();
    }, AGENCY_NAME);
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Scheme", "Core Research Grant (CRG)");
    await clickButtonWithText(page, "Save changes");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "Core Research Grant (CRG)", 15_000);
    check("agency edited (scheme update round-trips)", true);

    await page.evaluate((name) => {
      const button = [...document.querySelectorAll("button")].find(
        (btn) => btn.getAttribute("aria-label") === `Delete ${name}`,
      );
      button?.click();
    }, TRASH_AGENCY);
    await page.waitForSelector('[role="alertdialog"]', { timeout: 10_000 });
    await clickButtonWithText(page, "Delete", { inDialog: true });
    await page.waitForFunction(
      (name) => !document.body.innerText.includes(name),
      { timeout: 15_000 },
      TRASH_AGENCY,
    );
    check("agency deleted via the confirm dialog", true);

    // --------------------------------- dashboard reactivity after the flows
    await page.goto(`${BASE}/research`, { waitUntil: "networkidle0" });
    const dashAfter = await waitForText(page, PROJECT_TITLE_UI, 60_000);
    check(
      "dashboard is reactive (new project + deadlines panel after flows)",
      /TOTAL PROJECTS[\s\S]*TOTAL GRANTS/.test(dashAfter.toUpperCase()),
    );

    // --------------------------------------------------------- cleanliness
    const hostileApi = failedResponses.filter((line) => {
      if (!line.includes("/api/v1/")) return false;
      // Intentional checks above: duplicate project/agency 409s and the
      // budget-guard 422 are produced on purpose.
      if (line.startsWith("409 POST") && line.endsWith("/api/v1/research/projects")) return false;
      if (line.startsWith("409 POST") && line.endsWith("/api/v1/research/agencies")) return false;
      if (line.startsWith("422 POST") && line.includes("/installments")) return false;
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

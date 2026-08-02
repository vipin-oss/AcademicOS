/**
 * Faculty Management module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   faculty directory (PART 1 table with photo avatars + PART 7 token search
 *   and department/designation/employment/status filters) -> create via the
 *   modal (full record incl. a Degrees profile-section row + committee
 *   multi-select) -> duplicate employee id 409 in the modal -> the enriched
 *   workspace (header with scholar links, PART 6 dashboard cards, PART 2
 *   academic profile, PART 3 research lens, PART 4 supervision current/
 *   completed, PART 5 teaching load with weekly hours, committees,
 *   publications + documents lenses, audit) -> profile photo upload ->
 *   edit merge -> delete with flash -> 404 state.
 *
 * The cross-module graph (project, grant, students, class, publication,
 * document, committees) is seeded through the FROZEN modules' own APIs.
 *
 * Usage:
 *   node tests/faculty-e2e.mjs            # http://127.0.0.1:3000
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
const COMMITTEE_NAME = `IQAC E2E ${STAMP}`;
const COMMITTEE2_NAME = `NAAC E2E ${STAMP}`;
const FACULTY_NAME = `Dr. Asha Nair E2E ${STAMP}`;
const FACULTY_NAME_UI = `Dr. Kabir Shah E2E ${STAMP}`;
const EMPLOYEE_ID = `E2E-${STAMP}-EMP1`;
const EMPLOYEE_ID_UI = `E2E-${STAMP}-EMP2`;
const PROJECT_TITLE = `E2E Perovskite Cells ${STAMP}`;
const PROJECT_DONE = `E2E Quantum Dots ${STAMP}`;
const GRANT_TITLE = `E2E SERB Core Grant ${STAMP}`;
const STUDENT_NAME = `Ravi Kumar E2E ${STAMP}`;
const ALUM_NAME = `Meera Iyer E2E ${STAMP}`;
const CLASS_TITLE = `E2E Quantum Mechanics ${STAMP}`;
const PUB_TITLE = `E2E Quantum dots in perovskites ${STAMP}`;
const DOC_TITLE = `E2E Joining Letter ${STAMP}`;
const TRASH_NAME = `E2E Trash Faculty ${STAMP}`;

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

/** Click a link (or button) whose text matches exactly (row navigation). */
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

/** Read the big number of a PART 6 dashboard card by its label. */
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
  const committee = await postJson("/objects", {
    object_type: "committee",
    title: COMMITTEE_NAME,
    created_by: "registrar:e2e",
  }).then((r) => r.body);
  const committee2 = await postJson("/objects", {
    object_type: "committee",
    title: COMMITTEE2_NAME,
    created_by: "registrar:e2e",
  }).then((r) => r.body);
  check("seed: two committees created (IQAC + NAAC)", Boolean(committee.id && committee2.id));

  const facultyRes = await postJson("/faculty", {
    name: FACULTY_NAME,
    employee_id: EMPLOYEE_ID,
    uploaded_by: "registrar:e2e",
    status: "active",
    faculty_code: `E2E-${STAMP}-F01`,
    designation: "Associate Professor",
    department: "Physics",
    school: "School of Physical Sciences",
    joining_date: "2015-07-01",
    employment_type: "regular",
    email: "asha.nair@univ.edu",
    mobile: "+91-98xxxxxxx1",
    office: "B-204",
    qualification: "Ph.D. (Physics), IIT Delhi",
    specialization: "Condensed Matter Physics",
    research_interests: ["perovskites", "quantum dots"],
    biography: "Works on thin-film photovoltaics.",
    orcid: "0000-0002-1825-0097",
    scopus_id: "55512345600",
    website: "https://univ.edu/faculty/asha",
    tags: ["senate"],
    degrees: [{ degree: "Ph.D.", institution: "IIT Delhi", year: "2012" }],
    awards: [{ title: "Young Scientist Award", year: "2019", by: "INSA" }],
    links: { committees: [committee.id] },
  });
  const faculty = facultyRes.body;
  check(
    "seed: faculty created (full directory + sections + committee)",
    facultyRes.status === 201 &&
      faculty.employee_id === EMPLOYEE_ID &&
      faculty.degrees?.[0]?.institution === "IIT Delhi" &&
      faculty.links?.committees?.[0]?.id === committee.id,
    faculty.id ?? JSON.stringify(facultyRes.body),
  );

  const dupEmployee = await postJson("/faculty", {
    name: `Duplicate ${STAMP}`,
    employee_id: EMPLOYEE_ID.toLowerCase(),
    uploaded_by: "registrar:e2e",
  });
  check("seed: duplicate employee id rejected (409)", dupEmployee.status === 409);

  const dupCode = await postJson("/faculty", {
    name: `Duplicate2 ${STAMP}`,
    employee_id: `E2E-${STAMP}-EMP9`,
    faculty_code: `e2e-${STAMP}-f01`, // same code, different case -> 409
    uploaded_by: "registrar:e2e",
  });
  check("seed: duplicate faculty code rejected (409)", dupCode.status === 409);

  const badMail = await postJson("/faculty", {
    name: `BadMail ${STAMP}`,
    employee_id: `E2E-${STAMP}-EMP8`,
    email: "nope",
    uploaded_by: "registrar:e2e",
  });
  check("seed: invalid email rejected (422)", badMail.status === 422);

  const project = await postJson("/research/projects", {
    title: PROJECT_TITLE,
    uploaded_by: "registrar:e2e",
    lifecycle_status: "funded",
    team: {
      principal_investigators: [faculty.id],
      co_investigators: [],
      team_members: [],
    },
  }).then((r) => r.body);
  const projectDone = await postJson("/research/projects", {
    title: PROJECT_DONE,
    uploaded_by: "registrar:e2e",
    lifecycle_status: "completed",
    team: {
      principal_investigators: [],
      co_investigators: [],
      team_members: [faculty.id],
    },
  }).then((r) => r.body);
  check(
    "seed: funded project (PI) + completed project (team) linked",
    Boolean(project.id && projectDone.id),
    project.id ?? "",
  );

  const grant = await postJson("/research/grants", {
    title: GRANT_TITLE,
    grant_number: `E2E-${STAMP}-G01`,
    uploaded_by: "registrar:e2e",
    amount: 3_000_000,
    links: { projects: [project.id], funding_agencies: [] },
  }).then((r) => r.body);
  check("seed: grant funds the PI project", Boolean(grant.id), grant.id ?? "");

  const scholar = await postJson("/students", {
    name: STUDENT_NAME,
    student_type: "phd",
    roll_number: `E2E-${STAMP}-S01`,
    uploaded_by: "registrar:e2e",
    links: { supervisors: [faculty.id] },
  }).then((r) => r.body);
  const alum = await postJson("/students", {
    name: ALUM_NAME,
    student_type: "alumni",
    roll_number: `E2E-${STAMP}-S02`,
    uploaded_by: "registrar:e2e",
    links: { co_supervisors: [faculty.id] },
  }).then((r) => r.body);
  check(
    "seed: current PhD supervisee + completed alumnus linked",
    Boolean(scholar.id && alum.id),
  );

  const cls = await postJson("/teaching/classes", {
    title: CLASS_TITLE,
    uploaded_by: "registrar:e2e",
    course_code: "PHY-301",
    programme: "BSc Physics",
    semester: 3,
    credits: 4,
    weekly_schedule: [
      { day: "mon", start: "09:00", end: "10:30" },
      { day: "thu", start: "14:00", end: "15:00" },
    ],
    links: { teachers: [faculty.id] },
  }).then((r) => r.body);
  check("seed: class with a 2.5h weekly schedule linked", Boolean(cls.id), cls.id ?? "");

  const publication = await postJson("/publications", {
    title: PUB_TITLE,
    publication_type: "journal_article",
    uploaded_by: "registrar:e2e",
    authors: [{ name: "Asha Nair" }],
    links: { faculty: [faculty.id] },
  }).then((r) => r.body);
  check("seed: publication linked to the faculty", Boolean(publication.id), publication.id ?? "");

  const form = new FormData();
  form.append("title", DOC_TITLE);
  form.append("document_type", "pdf");
  form.append("uploaded_by", "registrar:e2e");
  form.append("object_id", faculty.id);
  form.append("file", new Blob([`joining letter ${STAMP}`], { type: "text/plain" }), "letter.txt");
  const document_ = await fetch(`${API}/documents`, { method: "POST", body: form }).then((r) =>
    r.json(),
  );
  check("seed: joining-letter document attached to the faculty", Boolean(document_.id));

  // Trash faculty for the delete flow (UI-visible).
  const trash = await postJson("/faculty", {
    name: TRASH_NAME,
    employee_id: `E2E-${STAMP}-EMP7`,
    uploaded_by: "registrar:e2e",
  }).then((r) => r.body);
  check("seed: trash faculty for the delete flow", Boolean(trash.id));

  // A 1x1 PNG for the photo upload.
  const pngPath = "/tmp/faculty-e2e-photo.png";
  fs.writeFileSync(
    pngPath,
    Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
      "base64",
    ),
  );

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
    // ---------------------------------------------------- faculty directory
    await page.goto(`${BASE}/faculty`, { waitUntil: "networkidle0" });
    await page.waitForSelector("h1", { timeout: 30_000 });
    const heading = await page.$eval("h1", (el) => el.textContent?.trim());
    check("faculty directory loads", heading?.includes("Faculty") ?? false, heading ?? "");
    const navText = await page.$eval("nav", (nav) => nav.innerText);
    check("sidebar exposes the Faculty entry", navText.includes("Faculty"));

    const tableText = await waitForText(page, FACULTY_NAME, 60_000);
    check(
      "directory table shows identity + designation + department + contact",
      tableText.includes(EMPLOYEE_ID) &&
        tableText.includes("Associate Professor") &&
        tableText.includes("Physics") &&
        tableText.includes("asha.nair@univ.edu"),
    );
    check(
      "directory table shows employment + status badges",
      tableText.includes("Regular") && tableText.includes("Active"),
    );

    // PART 7: token search
    await setFieldValue(page, 'input[type="search"]', `nonexistent-${STAMP}`);
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching faculty"),
      { timeout: 15_000 },
    );
    check("search: non-matching query shows the empty state", true);
    await setFieldValue(page, 'input[type="search"]', `quantum dots asha ${STAMP}`);
    await page.waitForFunction(
      (name) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === name),
      { timeout: 15_000 },
      FACULTY_NAME,
    );
    check("search: token-AND search finds the faculty (name + research area)", true);
    await setFieldValue(page, 'input[type="search"]', "");
    await sleep(600);

    // PART 7: department + designation + employment + status filters
    await setFieldValue(page, 'input[aria-label="Filter by department"]', "physics");
    await page.select('select[aria-label="Filter by designation"]', "Associate Professor");
    await page.select('select[aria-label="Filter by employment type"]', "regular");
    await page.select('select[aria-label="Filter by status"]', "active");
    await page.waitForFunction(
      (name) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === name),
      { timeout: 15_000 },
      FACULTY_NAME,
    );
    check(
      "filters: department + designation + employment + status combine",
      true,
    );
    await page.select('select[aria-label="Filter by designation"]', "Professor");
    await page.waitForFunction(
      (name) =>
        ![...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === name),
      { timeout: 15_000 },
      FACULTY_NAME,
    );
    check("filters: wrong designation excludes the faculty", true);
    await clickButtonWithText(page, "Clear filters");
    await sleep(600);

    // ------------------------------------------------ create via the modal
    await clickButtonWithText(page, "New Faculty");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Full name", FACULTY_NAME_UI);
    await typeInField(page, "Employee ID", EMPLOYEE_ID_UI);
    await typeInField(page, "Faculty code", `E2E-${STAMP}-F02`);
    await typeInField(page, "Designation", "Professor");
    await typeInField(page, "Department", "Mathematics");
    await typeInField(page, "Email", "kabir.shah@univ.edu");
    await typeInField(page, "Specialization", "Algebra");
    await typeInField(page, "Research interests", "number theory, algebra");
    await page.select('form[role="dialog"] select[aria-label="Employment type"]', "regular");
    // PART 2 rows editor: add a Degrees row and fill it.
    await clickButtonWithText(page, "Add degrees", { inDialog: true });
    await setFieldValue(page, 'input[aria-label="Degrees row 1 Degree"]', "Ph.D.");
    await setFieldValue(page, 'input[aria-label="Degrees row 1 Institution"]', "IIT Bombay");
    await setFieldValue(page, 'input[aria-label="Degrees row 1 Year"]', "2009");
    await waitForOption(
      page,
      'form[role="dialog"] select[aria-label="Committee memberships"]',
      committee2.id,
    );
    await page.select(
      'form[role="dialog"] select[aria-label="Committee memberships"]',
      committee2.id,
    );
    await clickButtonWithText(page, "Add faculty member");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await waitForText(page, "added successfully", 15_000);
    check("create: faculty added via the modal (toast)", true);
    await setFieldValue(page, 'input[type="search"]', `kabir ${STAMP}`);
    const kabirText = await waitForText(page, FACULTY_NAME_UI, 15_000);
    check(
      "create: new faculty appears in the directory (designation + dept)",
      kabirText.includes("Professor") && kabirText.includes("Mathematics"),
    );
    await setFieldValue(page, 'input[type="search"]', "");
    await sleep(600);

    // duplicate employee id -> backend 409 surfaces in the modal
    await clickButtonWithText(page, "New Faculty");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Full name", `Duplicate ${STAMP}`);
    await typeInField(page, "Employee ID", EMPLOYEE_ID);
    await clickButtonWithText(page, "Add faculty member");
    await page.waitForSelector('form[role="dialog"] [role="alert"]', { timeout: 15_000 });
    const dupeAlert = await page.$eval(
      'form[role="dialog"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check(
      "duplicate employee id surfaces the backend 409 in the modal",
      dupeAlert.toLowerCase().includes("duplicate"),
      dupeAlert.slice(0, 90),
    );
    await clickButtonWithText(page, "Cancel", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 10_000,
    });

    // ------------------------------------------------------ the workspace
    await setFieldValue(page, 'input[type="search"]', `asha ${STAMP}`);
    await page.waitForFunction(
      (name) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === name),
      { timeout: 15_000 },
      FACULTY_NAME,
    );
    await clickLinkWithText(page, FACULTY_NAME);
    const workspace = await waitForText(page, "STUDENTS SUPERVISED", 60_000);
    check(
      "workspace loads (header + employment badge + scholar links)",
      workspace.includes(FACULTY_NAME) &&
        workspace.includes("Associate Professor") &&
        workspace.includes("ORCID") &&
        workspace.includes("Regular"),
    );

    // PART 6 dashboard cards — server-computed stats for the seeded graph.
    check(
      "PART 6 cards render (publications/projects/grants/students/courses/committees)",
      /PUBLICATIONS[\s\S]*ACTIVE PROJECTS[\s\S]*RESEARCH GRANTS[\s\S]*STUDENTS SUPERVISED[\s\S]*COURSES[\s\S]*COMMITTEES/.test(
        workspace.toUpperCase(),
      ),
    );
    const statChecks = [
      ["PUBLICATIONS", "1"],
      ["ACTIVE PROJECTS", "1"],
      ["RESEARCH GRANTS", "1"],
      ["STUDENTS SUPERVISED", "1"],
      ["COURSES", "1"],
      ["COMMITTEES", "1"],
    ];
    let statsOk = true;
    let statDetail = "";
    for (const [label, expected] of statChecks) {
      const value = await cardValue(page, label);
      if (value !== expected) {
        statsOk = false;
        statDetail = `${label}=${value}`;
      }
    }
    check("PART 6 stats match the seeded graph (all six = 1)", statsOk, statDetail);

    // PART 2 academic profile
    check(
      "academic profile shows the degree + award lines",
      workspace.includes("Ph.D.") &&
        workspace.includes("IIT Delhi") &&
        workspace.includes("Young Scientist Award"),
    );

    // PART 3 research lens
    check(
      "research lens lists the PI project, the completed team project and the grant",
      workspace.includes(PROJECT_TITLE) &&
        workspace.includes(PROJECT_DONE) &&
        workspace.includes(GRANT_TITLE),
    );
    check(
      "research roles render (PI + Team badges)",
      workspace.includes("PI") && workspace.includes("Team"),
    );

    // PART 4 supervision lens
    check(
      "supervision splits current (PhD) vs completed (alumnus)",
      workspace.includes(STUDENT_NAME) &&
        workspace.includes(ALUM_NAME) &&
        workspace.toUpperCase().includes("CURRENT STUDENTS") &&
        workspace.toUpperCase().includes("COMPLETED STUDENTS"),
    );

    // PART 5 teaching load
    check(
      "teaching load lists the class with credits + 2.5 weekly hours",
      workspace.includes(CLASS_TITLE) &&
        workspace.includes("PHY-301") &&
        workspace.includes("2.5h"),
    );
    check(
      "teaching total weekly hours render",
      workspace.toUpperCase().includes("TOTAL: 2.5H/WEEK"),
    );

    // committees + lenses + audit
    check("committee membership (IQAC) renders", workspace.includes(COMMITTEE_NAME));
    check("publications lens lists the linked publication", workspace.includes(PUB_TITLE));
    check("documents lens lists the attached document", workspace.includes(DOC_TITLE));
    check(
      "audit info renders the Object id + version",
      workspace.includes("obj:faculty:") &&
        workspace.includes("Current version") &&
        /v\d+/.test(workspace),
    );

    // ------------------------------------------------------ profile photo
    const photoInput = await page.$('input[aria-label="Choose a profile photo"]');
    check("photo picker input present on the workspace", Boolean(photoInput));
    await photoInput.uploadFile(pngPath);
    await waitForText(page, "Profile photo updated", 20_000);
    await page.waitForSelector('img[alt*="Profile photo"]', { timeout: 15_000 });
    check("photo upload: avatar switches to the uploaded image", true);
    const photoSrc = await page.$eval('img[alt*="Profile photo"]', (img) => img.src);
    check("photo url points at the API blob route", photoSrc.includes("/faculty/"), photoSrc);
    const blobOk = await fetch(photoSrc).then((r) => r.status);
    check("photo blob is downloadable (200)", blobOk === 200, String(blobOk));

    // ---------------------------------------------------------- edit merge
    await clickButtonWithText(page, "Edit");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    const editName = await page.$eval(
      'form[role="dialog"] input',
      (input) => input.value,
    );
    check("edit modal prefills the current name", editName === FACULTY_NAME, editName);
    await typeInField(page, "Office", "C-101");
    await typeInField(page, "Specialization", "Photovoltaics");
    await clickButtonWithText(page, "Save changes");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    const merged = await waitForText(page, "C-101", 15_000);
    check(
      "edit merge: office replaced, untouched identity kept",
      merged.includes("C-101") &&
        merged.includes("Photovoltaics") &&
        merged.includes(EMPLOYEE_ID) &&
        merged.includes("Physics"),
    );

    // ------------------------------------------------------------- delete
    await page.goto(`${BASE}/faculty`, { waitUntil: "networkidle0" });
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
    check("delete: confirm dialog redirects with a flash toast", page.url().includes("/faculty"));
    await setFieldValue(page, 'input[type="search"]', `trash ${STAMP}`);
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching faculty"),
      { timeout: 15_000 },
    );
    check("delete: the faculty is gone from the directory", true);

    // --------------------------------------------------------- 404 state
    await page.goto(`${BASE}/faculty/${encodeURIComponent("obj:faculty:MISSING")}`, {
      waitUntil: "networkidle0",
    });
    await waitForText(page, "Faculty member not found", 30_000);
    check("404 state renders for a missing faculty id", true);

    // --------------------------------------------------------- cleanliness
    const hostileApi = failedResponses.filter((line) => {
      if (!line.includes("/api/v1/")) return false;
      // Intentional checks above: duplicate employee-id faculty 409s and the
      // duplicate-code-in-modal 409 + invalid-email 422 are produced on purpose.
      if (line.startsWith("409 POST") && line.endsWith("/api/v1/faculty")) return false;
      if (line.startsWith("422 POST") && line.endsWith("/api/v1/faculty")) return false;
      // The 404-state check above opens a deliberately missing id.
      if (line.startsWith("404 GET") && line.includes("/api/v1/faculty/obj:faculty:MISSING")) {
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

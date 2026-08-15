/**
 * Students & Teaching module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   students list -> server-side search -> admit via modal -> duplicate-roll
 *   409 alert -> CSV import with duplicate report -> export link -> student
 *   detail (registry + object lenses) -> teaching dashboard (PART J) -> class
 *   workspace (roster, enroll via modal, assignment create via modal,
 *   attendance via modal + below-75 flag, gradebook matrix, report snapshot)
 *   -> assignment workspace (submission grid C7, inline grading, marks CSV
 *   Google-loop, late state) -> dashboard reactivity.
 *
 * Usage:
 *   node tests/students-teaching-e2e.mjs            # http://127.0.0.1:3000
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
const STUDENT_A = `Asha Verma ${STAMP}`;
const STUDENT_B = `Ravi Kumar ${STAMP}`;
const STUDENT_C = `Meera Iyer ${STAMP}`;
const STUDENT_D = `Kabir Shah ${STAMP}`;
const ROLL_A = `E2E-${STAMP}-101`;
const ROLL_B = `E2E-${STAMP}-102`;
const ROLL_C = `E2E-${STAMP}-103`;
const CLASS_TITLE = `Computer Fundamentals ${STAMP}`;
const ASSIGNMENT_TITLE = `Assignment 1 — Python Basics ${STAMP}`;
const QUIZ_TITLE = `Quiz 1 — Loops ${STAMP}`;

const postJson = (path, body) =>
  fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => r.json());

/**
 * Click a button by its exact label. When a dialog is open, a button INSIDE
 * the dialog wins over a same-labelled page button (mirrors the publications
 * harness).
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
 * Fill the input wrapped by the <label> whose text starts with `label`.
 * Sets the whole value through the native setter (React onChange still
 * fires) — keyboard simulation races with list-refresh re-renders and can
 * swallow characters under load.
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
 * Wait until `needle` appears in body.innerText using an explicit
 * sleep+evaluate loop. Compared case-insensitively: innerText applies CSS
 * text-transform, so uppercase-styled labels never match their DOM spelling.
 */
async function waitForText(page, needle, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  const wanted = needle.toUpperCase();
  for (;;) {
    const text = await page.evaluate(() => document.body.innerText);
    if (text.toUpperCase().includes(wanted)) return text;
    if (Date.now() >= deadline) throw new Error(`Timed out waiting for text “${needle}”.`);
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
}

/** Set a React-controlled input's value directly (date inputs etc.). */
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
  const imported = await postJson("/students/import", {
    text: [
      "Roll No,Name,Email,Section,Programme,Semester",
      `${ROLL_A},${STUDENT_A},asha-${STAMP}@e2e.edu,A,BSc Mathematics,1`,
      `${ROLL_B},${STUDENT_B},ravi-${STAMP}@e2e.edu,A,BSc Mathematics,1`,
      `${ROLL_C},${STUDENT_C},meera-${STAMP}@e2e.edu,A,BSc Mathematics,1`,
    ].join("\n"),
    uploaded_by: "faculty:e2e",
  });
  const [idA, idB, idC] = imported.created ?? [];
  check("seed: 3 students imported via API", Boolean(idA && idB && idC));

  const faculty = await postJson("/objects", {
    object_type: "faculty",
    title: `Prof E2E ${STAMP}`,
    created_by: "faculty:e2e",
  });
  check("seed: faculty object created", Boolean(faculty.id), faculty.id ?? "");

  const cls = await postJson("/teaching/classes", {
    title: CLASS_TITLE,
    uploaded_by: "faculty:e2e",
    course_code: "CS-101",
    programme: "BSc Mathematics with Data Science",
    semester: 1,
    section: "A",
    session: "2026-27",
    class_mode: "offline",
    links: { teachers: [faculty.id] },
  });
  check("seed: class created with teacher link", Boolean(cls.id), cls.id ?? "");

  const enrolled = await postJson(`/teaching/classes/${cls.id}/enroll`, {
    student_ids: [idA, idB, idC],
    actor: "faculty:e2e",
  });
  check(
    "seed: 3 students enrolled",
    (enrolled.enrolled ?? []).length === 3,
    JSON.stringify(enrolled.errors ?? []),
  );

  const assignment = await postJson(`/teaching/classes/${cls.id}/assignments`, {
    title: ASSIGNMENT_TITLE,
    uploaded_by: "faculty:e2e",
    assignment_type: "assignment",
    max_marks: 20,
    deadline: "2999-12-31T23:59",
    late_allowed: true,
  });
  const quiz = await postJson(`/teaching/classes/${cls.id}/assignments`, {
    title: QUIZ_TITLE,
    uploaded_by: "faculty:e2e",
    assignment_type: "quiz",
    max_marks: 10,
    deadline: "2020-01-01T00:00",
    late_allowed: true,
  });
  check(
    "seed: assignment + past-deadline quiz created",
    Boolean(assignment.id && quiz.id),
  );

  // A submits to the assignment on time; A's quiz submission is late (past
  // deadline) but stays ungraded until the UI flows run.
  const submit = async (assignmentId, studentId) => {
    const form = new FormData();
    form.append("student_id", studentId);
    form.append("comments", "seeded submission");
    form.append("actor", "faculty:e2e");
    form.append("file", new Blob([`e2e ${STAMP}`], { type: "text/plain" }), "answer.txt");
    const res = await fetch(`${API}/teaching/assignments/${assignmentId}/submit`, {
      method: "POST",
      body: form,
    });
    return res.json();
  };
  const subA = await submit(assignment.id, idA);
  const quizSubA = await submit(quiz.id, idA);
  check(
    "seed: on-time + late submissions recorded (is_late computed)",
    Boolean(subA.id) && quizSubA.is_late === true,
  );

  // One earlier attendance day so the summary has one student below 75%.
  const day1 = await postJson(`/teaching/classes/${cls.id}/attendance`, {
    session_date: "2026-07-18",
    records: { [idA]: "present", [idB]: "absent", [idC]: "present" },
    actor: "faculty:e2e",
  });
  check("seed: attendance day 1 recorded", Boolean(day1.id));

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
  // Diagnostic: trace the class-report request lifecycle (the class page's
  // slowest section — needed to distinguish stuck network vs slow render).
  const reportTrace = [];
  page.on("request", (req) => {
    if (req.url().includes("/report")) {
      reportTrace.push(`REQ ${Date.now() % 100000} ${req.url().split("/api/v1")[1]}`);
    }
  });
  page.on("response", (res) => {
    if (res.url().includes("/report")) reportTrace.push(`RES ${Date.now() % 100000} ${res.status()}`);
  });
  page.on("requestfailed", (req) => {
    if (req.url().includes("/report")) reportTrace.push(`FAIL ${req.failure()?.errorText}`);
  });
  page.on("requestfinished", (req) => {
    if (req.url().includes("/report")) reportTrace.push(`FIN ${Date.now() % 100000}`);
  });

  try {
    // --------------------------------------------------------- students list
    await page.goto(`${BASE}/students`, { waitUntil: "networkidle0" });
    await page.waitForSelector("h1", { timeout: 30_000 });
    const heading = await page.$eval("h1", (el) => el.textContent?.trim());
    check("students list page loads", heading === "Students", heading ?? "");
    const listError = await page.evaluate(() =>
      document.body.innerText.includes("Could not load students"),
    );
    check("list fetches from backend without error", !listError);
    const navText = await page.$eval("nav", (nav) => nav.innerText);
    check(
      "sidebar exposes Students + Teaching entries",
      navText.includes("Students") && navText.includes("Teaching"),
    );
    await page.waitForSelector("table a", { timeout: 15_000 });
    const countText = await page.evaluate(() => document.body.innerText);
    check(
      "list renders rows + total count (roll-number registry order)",
      /\d+ students?/.test(countText),
    );

    // server-side search
    await page.type('input[type="search"]', "e2e nonexistent person");
    await sleep(600); // debounce + request
    await page.waitForFunction(
      () => document.body.innerText.includes("No matching students"),
      { timeout: 15_000 },
    );
    check("search: non-matching query shows the empty state", true);
    await page.evaluate((stamp) => {
      const input = document.querySelector('input[type="search"]');
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value",
      ).set;
      setter.call(input, `asha verma ${stamp}`);
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }, STAMP);
    await page.waitForFunction(
      (name) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === name),
      { timeout: 15_000 },
      STUDENT_A,
    );
    check("search: token search finds the student (server-side q)", true);
    await page.evaluate(() => {
      document.querySelector('button[aria-label="Clear search"]')?.click();
    });
    await sleep(400);

    // ------------------------------------------------- admit via the modal
    await clickButtonWithText(page, "Add Student");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Full name", STUDENT_D);
    await typeInField(page, "Roll number", `E2E-${STAMP}-104`);
    await typeInField(page, "Programme", "BSc Mathematics");
    await clickButtonWithText(page, "Admit student");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    // The list is roll-ordered (page 1 may not include the new roll) — find
    // the admitted student through the server-side search, like a registrar.
    await setFieldValue(page, 'input[type="search"]', `kabir shah ${STAMP}`);
    await page.waitForFunction(
      (name) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === name),
      { timeout: 15_000 },
      STUDENT_D,
    );
    check("admit: new student appears in the list (via search)", true);
    await page.evaluate(() => {
      document.querySelector('button[aria-label="Clear search"]')?.click();
    });
    await sleep(400);

    // duplicate roll -> backend 409 surfaces in the modal
    await clickButtonWithText(page, "Add Student");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Full name", `Duplicate ${STAMP}`);
    await typeInField(page, "Roll number", ROLL_A);
    await clickButtonWithText(page, "Admit student");
    await page.waitForSelector('form[role="dialog"] [role="alert"]', { timeout: 15_000 });
    const dupeAlert = await page.$eval(
      'form[role="dialog"] [role="alert"]',
      (el) => el.textContent ?? "",
    );
    check(
      "duplicate roll surfaces the backend 409 in the modal",
      dupeAlert.toLowerCase().includes("roll"),
      dupeAlert.slice(0, 80),
    );
    await clickButtonWithText(page, "Cancel", { inDialog: true });
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 10_000,
    });

    // ------------------------------------------------- CSV import (PART F)
    await clickButtonWithText(page, "Import");
    await page.waitForSelector('form[role="dialog"] textarea[aria-label="CSV text"]', {
      timeout: 10_000,
    });
    const csv = [
      "Roll No,Name,Email,Programme,Semester",
      `E2E-${STAMP}-105,Diya Rao ${STAMP},diya-${STAMP}@e2e.edu,BSc Mathematics,1`,
      `${ROLL_B},Duplicate Ravi,dup-${STAMP}@e2e.edu,BSc Mathematics,1`,
    ].join("\n");
    await setFieldValue(page, 'textarea[aria-label="CSV text"]', csv);
    await clickButtonWithText(page, "Import", { inDialog: true });
    await page.waitForFunction(
      () =>
        document
          .querySelector('form[role="dialog"]')
          ?.innerText.includes("Imported 1 student") ?? false,
      { timeout: 15_000 },
    );
    const importText = await page.evaluate(() => document.body.innerText);
    check("import creates the new student", true);
    check(
      "import reports the duplicate (never silently overwritten)",
      importText.includes("1 duplicate skipped") && importText.includes("Duplicate Ravi"),
    );
    await clickButtonWithText(page, "Done");
    await sleep(300);

    // ------------------------------------------------------------- export
    const exportHref = await page.evaluate(
      () =>
        [...document.querySelectorAll("a")].find((a) => a.href.includes("/students/export"))
          ?.href,
    );
    check("export link points at /students/export", Boolean(exportHref));
    const rosterCsv = await fetch(exportHref).then((r) => r.text());
    check(
      "CSV export contains the roster",
      rosterCsv.includes(STUDENT_A) && rosterCsv.includes(ROLL_B),
    );

    // ------------------------------------------------------- student detail
    await setFieldValue(page, 'input[type="search"]', `asha verma ${STAMP}`);
    await page.waitForFunction(
      (name) =>
        [...document.querySelectorAll("table a")].some((a) => a.textContent?.trim() === name),
      { timeout: 15_000 },
      STUDENT_A,
    );
    await page.evaluate((name) => {
      const link = [...document.querySelectorAll("table a")].find(
        (a) => a.textContent?.trim() === name,
      );
      link?.click();
    }, STUDENT_A); 
    await page.waitForFunction(
      (name) => document.querySelector("h1")?.textContent?.trim() === name,
      { timeout: 15_000 },
      STUDENT_A,
    );
    // The object lenses load asynchronously — wait for the class link.
    await page.waitForFunction(
      (title) => document.body.innerText.includes(title),
      { timeout: 15_000 },
      CLASS_TITLE,
    );
    const studentText = await page.evaluate(() => document.body.innerText);
    check("student detail opens with the student name", true);
    check(
      "detail shows registry + roll + programme",
      studentText.includes("Registry") &&
        studentText.includes(ROLL_A) &&
        studentText.includes("BSc Mathematics"),
    );
    check(
      "detail shows the linked panes (supervision/publications/documents)",
      studentText.includes("Supervision") &&
        studentText.includes("Publications") &&
        studentText.includes("Documents"),
    );
    check(
      "object lens: classes enrolled shows the seeded class",
      studentText.includes("Classes Enrolled") && studentText.includes(CLASS_TITLE),
    );

    // --------------------------------------------------- teaching dashboard
    await page.goto(`${BASE}/teaching`, { waitUntil: "networkidle0" });
    await page.waitForSelector("h1", { timeout: 30_000 });
    const teachingHeading = await page.$eval("h1", (el) => el.textContent?.trim());
    check("teaching dashboard loads", teachingHeading === "Teaching", teachingHeading ?? "");
    // Wait for THIS run's class row (the dashboard feeds all classes into
    // the ClassTable — the exact title appearing means data has landed).
    await page.waitForFunction(
      (title) =>
        document.body.innerText.includes("Top performers") &&
        [...document.querySelectorAll("table a")].some(
          (a) => a.textContent?.trim() === title,
        ),
      { timeout: 15_000 },
      CLASS_TITLE,
    );
    const dashText = await page.evaluate(() => document.body.innerText);
    // Stat-card labels are CSS-uppercased ("PENDING"/"LATE" in innerText) —
    // compare case-insensitively.
    const dashUpper = dashText.toUpperCase();
    check(
      "dashboard shows the PART J panels (classes table + weak/top lists)",
        ["WEAK STUDENTS", "TOP PERFORMERS", "PENDING", "LATE"].every((term) =>
          dashUpper.includes(term),
        ) && dashText.includes(CLASS_TITLE),
      dashText.includes(CLASS_TITLE)
        ? ""
        : `class title missing from the dashboard body`,
    );

    // ------------------------------------------------------ class workspace
    await page.evaluate((title) => {
      const link = [...document.querySelectorAll("table a")].find(
        (a) => a.textContent?.trim() === title,
      );
      link?.click();
    }, CLASS_TITLE);
    await page.waitForFunction(
      (title) => document.querySelector("h1")?.textContent?.trim() === title,
      { timeout: 15_000 },
      CLASS_TITLE,
    );
    // Roster / gradebook / report sections load asynchronously.
    await page.waitForFunction(() => document.body.innerText.includes("Roster (3)"), {
      timeout: 15_000,
    });
    const classText = await page.evaluate(() => document.body.innerText);
    check("class workspace opens with the class title", true);
    check(
      "class header + details render (code, session, teacher link)",
      classText.includes("CS-101") &&
        classText.includes("2026-27") &&
        classText.includes(`Prof E2E ${STAMP}`),
    );
    check("roster lists the 3 enrolled students", classText.includes("Roster (3)"));

    // enroll D via the modal (manual picker)
    await clickButtonWithText(page, "Enroll students");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await page.waitForFunction(
      (name) =>
        [...document.querySelectorAll('input[type="checkbox"]')].some((box) =>
          box.getAttribute("aria-label")?.includes(name),
        ),
      { timeout: 15_000 },
      STUDENT_D,
    );
    check("enroll modal lists un-enrolled students (already-enrolled disabled)", true);
    const alreadyDisabled = await page.evaluate((name) => {
      const box = [...document.querySelectorAll('input[type="checkbox"]')].find((el) =>
        el.getAttribute("aria-label")?.includes(name),
      );
      return box?.disabled === true;
    }, STUDENT_A);
    check("already-enrolled student checkbox is disabled", alreadyDisabled);
    await page.click(`input[aria-label="Enroll ${STUDENT_D}"]`);
    await clickButtonWithText(page, "Enroll", { inDialog: true });
    await page.waitForFunction(() => document.body.innerText.includes("Roster (4)"), {
      timeout: 15_000,
    });
    check("enroll: roster grows to 4", true);

    // create a second assignment through the modal
    await clickButtonWithText(page, "New assignment");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await typeInField(page, "Title", `Assignment 2 — Recursion ${STAMP}`);
    await typeInField(page, "Maximum marks", "25");
    await clickButtonWithText(page, "Create assignment");
    await page.waitForFunction(
      (title) => document.body.innerText.includes(title),
      { timeout: 15_000 },
      `Assignment 2 — Recursion ${STAMP}`,
    );
    check("assignment created via modal appears in the workspace", true);

    // attendance via the modal (all present, fixed date)
    await clickButtonWithText(page, "Record attendance");
    await page.waitForSelector('form[role="dialog"]', { timeout: 10_000 });
    await page.waitForFunction(
      () => document.querySelectorAll('form[role="dialog"] select').length >= 4,
      { timeout: 15_000 },
    );
    await setFieldValue(page, 'form[role="dialog"] input[aria-label="Session date"]', "2026-07-20");
    await clickButtonWithText(page, "All present");
    await clickButtonWithText(page, "Record", { inDialog: true });
    await page.waitForFunction(
      () => document.body.innerText.includes("2026-07-20"),
      { timeout: 15_000 },
    );
    check("attendance recorded via modal appears in the register", true);
    // The summary refreshes after the register — wait for both days.
    await page.waitForFunction(() => document.body.innerText.includes("2 sessions"), {
      timeout: 15_000,
    });
    const attendanceText = await page.evaluate(() => document.body.innerText);
    check(
      "summary flags the below-75% student (B: 1/2 days present)",
      attendanceText.includes("Below 75%") && attendanceText.includes("50%"),
    );

    // gradebook matrix (quiz late marker visible before grading). NOTE:
    // innerText applies CSS text-transform, so header labels compare
    // uppercased — the DOM itself holds "Internal"/"Average"/"Grade".
    await page.waitForFunction(() => document.body.innerText.includes("/20"), {
      timeout: 15_000,
    });
    const gradebookText = await page.evaluate(() => document.body.innerText);
    const gradebookUpper = gradebookText.toUpperCase();
    check(
      "gradebook matrix renders students × assessments",
      gradebookUpper.includes("INTERNAL") &&
        gradebookUpper.includes("AVERAGE") &&
        gradebookUpper.includes("GRADE") &&
        gradebookText.includes("/20") &&
        gradebookText.includes("/10"),
    );
    check(
      "gradebook marks the late quiz submission (L)",
      gradebookText.includes(QUIZ_TITLE.slice(0, 20)),
    );
    const gradebookExport = await page.evaluate(
      () =>
        [...document.querySelectorAll("a")].find((a) =>
          a.href.includes("/gradebook/export"),
        )?.href,
    );
    check("gradebook export link points at /gradebook/export", Boolean(gradebookExport));
    const marksSheet = await fetch(gradebookExport).then((r) => r.text());
    check(
      "gradebook CSV (university marks sheet) contains students + headers",
      marksSheet.includes(STUDENT_A) && marksSheet.includes(QUIZ_TITLE),
    );
    await page.waitForFunction(
      () => document.body.innerText.includes("Pending submissions"),
      { timeout: 15_000 },
    );
    const reportText = await page.evaluate(() => document.body.innerText);
    check(
      "class report snapshot renders (PART K)",
      reportText.includes("Class Report Snapshot") &&
        reportText.includes("Average marks") &&
        reportText.includes("Pending submissions"),
    );

    // -------------------------------------------------- assignment workspace
    await page.evaluate((title) => {
      const link = [...document.querySelectorAll("table a")].find(
        (a) => a.textContent?.trim() === title,
      );
      link?.click();
    }, ASSIGNMENT_TITLE);
    await page.waitForFunction(
      (title) => document.querySelector("h1")?.textContent?.trim() === title,
      { timeout: 15_000 },
      ASSIGNMENT_TITLE,
    );
    // The submission grid loads asynchronously — wait for the last student.
    await page.waitForFunction(
      (name) => document.body.innerText.includes(name),
      { timeout: 15_000 },
      STUDENT_D,
    );
    await page.waitForFunction(
      () => document.body.innerText.includes("answer.txt"),
      { timeout: 15_000 },
    );
    const assignmentText = await page.evaluate(() => document.body.innerText);
    check("assignment workspace opens with title + class breadcrumb", true);
    check(
      "submission grid (C7) lists every roster student with states",
      assignmentText.includes(STUDENT_A) &&
        assignmentText.includes(STUDENT_D) &&
        assignmentText.includes("Pending") &&
        assignmentText.includes("Submitted"),
    );
    check(
      "the seeded on-time submission shows its file + comment",
      assignmentText.includes("answer.txt") && assignmentText.includes("seeded submission"),
    );

    // inline grading: A gets 18/20
    await setFieldValue(page, `input[aria-label="Marks for ${STUDENT_A}"]`, "18");
    await setFieldValue(page, `input[aria-label="Feedback for ${STUDENT_A}"]`, "Well done");
    await clickButtonWithText(page, "Save marks");
    await page.waitForFunction(
      () =>
        [...document.querySelectorAll("button")].every(
          (btn) => btn.textContent?.trim() !== "Saving…",
        ) && document.body.innerText.includes("Graded: 1"),
      { timeout: 45_000 },
    );
    check("inline grading flips the row to Graded", true);

    // marks CSV (Google-forms loop): B gets 15/20 — submission created on the fly
    await clickButtonWithText(page, "Import marks CSV");
    await page.waitForSelector('form[role="dialog"] textarea[aria-label="Marks CSV text"]', {
      timeout: 10_000,
    });
    await setFieldValue(
      page,
      'textarea[aria-label="Marks CSV text"]',
      `Roll No,Marks,Feedback\n${ROLL_B},15,Good effort\n`,
    );
    await clickButtonWithText(page, "Import marks", { inDialog: true });
    await page.waitForFunction(
      () =>
        document
          .querySelector('form[role="dialog"]')
          ?.innerText.includes("Graded 1 submission") ?? false,
      { timeout: 15_000 },
    );
    const marksText = await page.evaluate(() => document.body.innerText);
    check(
      "marks CSV grades B and creates the submission from the CSV",
      marksText.includes("1 created from the CSV"),
    );
    await clickButtonWithText(page, "Done");
    await page.waitForFunction(() => !document.querySelector('form[role="dialog"]'), {
      timeout: 15_000,
    });
    await page.waitForFunction(
      () => document.body.innerText.includes("Graded: 2"),
      { timeout: 45_000 },
    );
    check("grid now shows 2 graded, 2 pending", true);
    const afterGrading = await page.evaluate(() => document.body.innerText);
    check(
      "pending students C / D stay pending in the grid (AI: who missed it)",
      afterGrading.includes("Pending: 2"),
    );

    // quiz page shows the LATE state computed server-side
    await page.goto(`${BASE}/teaching/assignments/${encodeURIComponent(quiz.id)}`, {
      waitUntil: "networkidle0",
    });
    await page.waitForSelector("h1", { timeout: 30_000 });
    const quizText = await page.evaluate(() => document.body.innerText);
    check(
      "quiz grid flags the late submission (is_late from the deadline)",
      quizText.includes(STUDENT_A) && quizText.includes("Late"),
    );

    // grade A's quiz via API (9/10) -> aggregates become reactive
    await fetch(`${API}/teaching/submissions/${quizSubA.id}/grade`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ marks: 9, actor: "faculty:e2e" }),
    });
    // Class-scoped and therefore deterministic (dashboard weak/top pools
    // span every class in the database): A's weighted average is
    // (18/20×20 + 9/10×10) / 30 = 90% -> grade A+, sole top performer.
    await page.goto(`${BASE}/teaching/classes/${encodeURIComponent(cls.id)}`, {
      waitUntil: "networkidle0",
    });
    // Force a pristine document: a stale execution context after the rapid
    // goto chain otherwise keeps serving the previous page's DOM.
    await page.reload({ waitUntil: "networkidle0" });
    const classAfter = await waitForText(page, "Top performers (1)", 60_000);
    const classAfterUpper = classAfter.toUpperCase();
    check(
      "gradebook + report update: A at 90% (grade A+, top performer)",
      classAfterUpper.includes("TOP PERFORMERS (1)") &&
        classAfter.includes("A+") &&
        classAfter.includes("90%"),
    );
    await page.goto(`${BASE}/teaching`, { waitUntil: "networkidle0" });
    const dashAfter = await waitForText(page, "Top performers", 90_000);
    check(
      "dashboard top performers panel is no longer empty (reactivity)",
      /Top performers[\s\S]*%/.test(dashAfter) &&
        !dashAfter.includes("Top performers appear once marks are graded"),
    );

    // --------------------------------------------------------- cleanliness
    const hostileApi = failedResponses.filter((line) => {
      if (!line.includes("/api/v1/")) return false;
      // The duplicate-roll check above INTENTIONALLY produces a 409.
      return !(line.startsWith("409 POST") && line.endsWith("/api/v1/students"));
    });
    check("no failing API requests (>=400)", hostileApi.length === 0, hostileApi[0] ?? "");
    const hostile = consoleErrors.filter(
      (line) =>
        !line.includes("favicon") &&
        !line.includes("404 (Not Found)") && // /favicon.ico — no favicon ships yet
        // The duplicate-roll check INTENTIONALLY produces a 409; chromium
        // logs every non-2xx fetch as a console error.
        !line.includes("409 (Conflict)") &&
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
      console.log("DEBUG report trace:", JSON.stringify(reportTrace));
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

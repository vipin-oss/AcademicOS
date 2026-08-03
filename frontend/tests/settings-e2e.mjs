/**
 * Settings & Preferences module smoke test (Puppeteer).
 *
 * Drives the real UI against a running backend + `next start`:
 *   sidebar entry -> PART 9 settings page (9 section cards render)
 *   -> Profile (PART 1): full field save -> API parity -> reload persistence,
 *      client-side invalid-email gate (no request leaves the page)
 *   -> Profile photo (PART 1): multipart upload -> binary preview ->
 *      byte-parity blob fetch -> remove -> placeholder restored (plus
 *      server-side rejection of a text file, verified at the API)
 *   -> Appearance (PART 2): dark theme applies `.dark` to <html> instantly,
 *      survives a reload via the root-layout ThemeEffect, light clears it;
 *      custom_theme stored (future-ready, never applied)
 *   -> Academic defaults (PART 3), Notification preferences (PART 4),
 *      Dashboard preferences (PART 5), Search preferences (PART 7, including
 *      the client-side JSON gate for saved filters), Privacy (PART 8),
 *      AI & personalization (PART 10: stored-inactive badge) — every save is
 *      asserted for API parity against GET /settings
 *   -> Backup & restore (PART 6): export contract (version/app/8 sections,
 *      photo omitted), UI import of a crafted file (confirm dialog -> merge
 *      of only the provided sections), UI reset to factory defaults
 *   -> cleanliness gates: zero failed API calls, zero console/page errors.
 *
 * The suite resets the settings singleton through the module's own API
 * before AND after the tour, so it composes with the other E2E suites in a
 * shared canonical database (settings are a singleton — no baseline+delta
 * counters needed anywhere else).
 *
 * Usage:
 *   node tests/settings-e2e.mjs         # http://localhost:3000
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

const STAMP = Date.now().toString(36);
const L = (label) => `${label} E2E ${STAMP}`;
const PROFILE = {
  name: L("Dr. Meera Iyer"),
  email: `meera.iyer.${STAMP}@university.edu`,
  designation: "Associate Professor",
  department: "Computer Science",
  institution: "AcademicOS University",
  biography: "Works on knowledge graphs and academic operating systems.",
};
const PHOTO_PATH = "/tmp/settings-e2e-photo.png";
const PHOTO_BYTES = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  Buffer.alloc(32, 0x30),
]);
const IMPORT_PATH = "/tmp/settings-e2e-import.json";
const IMPORT_NAME = L("Imported Name");
const SAVED_FILTERS = { objects: { status: "active" } };

// ---------------------------------------------------------------- helpers
const getJson = (path) =>
  fetch(`${API}${path}`).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

const postJson = (path, body, method = "POST") =>
  fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

async function waitForText(page, text, timeoutMs = 15_000) {
  await page.waitForFunction(
    (wanted) => document.body.innerText.includes(wanted),
    { timeout: timeoutMs },
    text,
  );
  return true;
}

/** wait until `section[aria-label=sel]`'s text contains `text`. */
async function waitForSectionText(page, sectionLabel, text, timeoutMs = 15_000) {
  await page.waitForFunction(
    (label, wanted) => {
      const el = document.querySelector(`section[aria-label="${label}"]`);
      return !!el && el.textContent.includes(wanted);
    },
    { timeout: timeoutMs },
    sectionLabel,
    text,
  );
  return true;
}

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

/** Click any element by aria-label (buttons, checkboxes, radios). */
async function clickAria(page, ariaLabel) {
  const clicked = await page.evaluate((wanted) => {
    const el = document.querySelector(`[aria-label="${wanted}"]`);
    if (!el) return false;
    el.click();
    return true;
  }, ariaLabel);
  if (!clicked) throw new Error(`Element aria-label “${ariaLabel}” missing`);
  return true;
}

const ariaChecked = (page, ariaLabel) =>
  page.evaluate(
    (wanted) => document.querySelector(`[aria-label="${wanted}"]`)?.getAttribute("aria-checked"),
    ariaLabel,
  );

const inputValue = (page, selector) =>
  page.evaluate((sel) => document.querySelector(sel)?.value ?? null, selector);

const isChecked = (page, ariaLabel) =>
  page.evaluate(
    (wanted) => document.querySelector(`[aria-label="${wanted}"]`)?.checked ?? null,
    ariaLabel,
  );

const htmlHasDark = (page) =>
  page.evaluate(() => document.documentElement.classList.contains("dark"));

/** Set a controlled input/select/textarea value the React-safe way. */
async function setInputValue(page, selector, value) {
  await page.waitForSelector(selector, { timeout: 15_000 });
  await page.evaluate(
    (sel, val) => {
      const el = document.querySelector(sel);
      if (!el) throw new Error(`input ${sel} missing`);
      const prototype =
        el instanceof HTMLTextAreaElement
          ? HTMLTextAreaElement.prototype
          : el instanceof HTMLSelectElement
            ? HTMLSelectElement.prototype
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

/** Accept the next native dialog (confirm). */
function armDialog(page) {
  page.once("dialog", (dialog) => {
    void dialog.accept();
  });
}

async function main() {
  fs.writeFileSync(PHOTO_PATH, PHOTO_BYTES);

  // ------------------------------------------------ deterministic baseline
  const reset = await postJson("/settings/reset", {});
  if (reset.status !== 200) throw new Error(`baseline reset failed: ${reset.status}`);
  // A previous run may have crashed mid-photo-story — the photo survives a
  // settings reset BY DESIGN, so clear it explicitly for a known start state.
  await fetch(`${API}/settings/profile/photo`, { method: "DELETE" }).catch(() => {});
  const baseline = (await getJson("/settings")).body;
  check(
    "api: baseline document has the 8 sections at factory defaults",
    reset.status === 200 &&
      Object.keys(baseline.sections).length === 8 &&
      baseline.sections.appearance.theme === "system" &&
      baseline.sections.search.recent_searches_limit === 10 &&
      baseline.has_photo === false,
    `sections=${Object.keys(baseline.sections ?? {}).length} theme=${baseline.sections?.appearance?.theme}`,
  );

  // API-level photo validation (server side; the UI picker filters by accept too)
  const badForm = new FormData();
  badForm.append("file", new Blob(["not an image"], { type: "text/plain" }), "note.txt");
  const badUpload = await fetch(`${API}/settings/profile/photo`, { method: "POST", body: badForm });
  check("api: photo upload rejects a non-image payload (422)", badUpload.status === 422, String(badUpload.status));
  await badUpload.arrayBuffer();

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
    // ------------------------------------------------ sidebar -> settings
    await page.goto(`${BASE}/events`, { waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Events & Academic Activities", 30_000);
    await clickLinkWithText(page, "Settings");
    await waitForText(page, "Settings & Preferences", 30_000);
    check("sidebar: Settings entry navigates to the settings page", page.url().endsWith("/settings"), page.url());

    const sectionLabels = await page.$$eval("main section[aria-label]", (els) =>
      els.map((el) => el.getAttribute("aria-label")),
    );
    const expectedSections = [
      "Profile",
      "Appearance",
      "Academic defaults",
      "Notification preferences",
      "Dashboard preferences",
      "Search preferences",
      "Privacy",
      "AI & personalization",
      "Backup & restore",
    ];
    check(
      "page: all 9 section cards render",
      expectedSections.every((label) => sectionLabels.includes(label)),
      sectionLabels.join(", "),
    );
    check(
      "page: defaults render (empty name, system theme, notifications on)",
      (await inputValue(page, 'input[aria-label="Profile name"]')) === "" &&
        (await ariaChecked(page, "Theme system")) === "true" &&
        (await isChecked(page, "Notifications enabled")) === true,
    );
    check(
      "page: copy states notifications stay in-app (no email/push)",
      await page.evaluate(() => document.body.innerText.includes("does not send email or push")),
    );

    // ------------------------------------------------ PART 1 profile fields
    await setInputValue(page, 'input[aria-label="Profile name"]', PROFILE.name);
    await setInputValue(page, 'input[aria-label="Profile email"]', "not-an-email");
    await clickAria(page, "Save profile");
    await waitForSectionText(page, "Profile", "Enter a valid email address", 10_000);
    check("profile: invalid email is blocked client-side (no request, inline error)", true);

    await setInputValue(page, 'input[aria-label="Profile email"]', PROFILE.email);
    await setInputValue(page, 'input[aria-label="Profile designation"]', PROFILE.designation);
    await setInputValue(page, 'input[aria-label="Profile department"]', PROFILE.department);
    await setInputValue(page, 'input[aria-label="Profile institution"]', PROFILE.institution);
    await setInputValue(page, 'textarea[aria-label="Profile biography"]', PROFILE.biography);
    await clickAria(page, "Save profile");
    await waitForSectionText(page, "Profile", "Saved.", 10_000);
    let doc = (await getJson("/settings")).body;
    check(
      "profile: save round-trips to the API",
      doc.sections.profile.name === PROFILE.name &&
        doc.sections.profile.email === PROFILE.email &&
        doc.sections.profile.designation === PROFILE.designation &&
        doc.sections.profile.department === PROFILE.department &&
        doc.sections.profile.institution === PROFILE.institution &&
        doc.sections.profile.biography === PROFILE.biography,
      JSON.stringify(doc.sections.profile),
    );

    // ------------------------------------------------ PART 1 photo lifecycle
    const photoInput = await page.$('input[aria-label="Profile photo file"]');
    check("photo: picker input present", Boolean(photoInput));
    await photoInput.uploadFile(PHOTO_PATH);
    await waitForSectionText(page, "Profile", "Photo updated.", 20_000);
    await page.waitForSelector('img[aria-label="Profile photo preview"]', { timeout: 15_000 });
    const photoSrc = await page.$eval('img[aria-label="Profile photo preview"]', (img) => img.src);
    check(
      "photo: upload switches the preview to the API blob route",
      photoSrc.includes("/settings/profile/photo"),
      photoSrc,
    );
    const blob = await fetch(photoSrc).then(async (r) => ({
      status: r.status,
      bytes: Buffer.from(await r.arrayBuffer()),
    }));
    check(
      "photo: blob downloads with byte parity",
      blob.status === 200 && blob.bytes.equals(PHOTO_BYTES),
      `status=${blob.status} bytes=${blob.bytes.length}/${PHOTO_BYTES.length}`,
    );
    doc = (await getJson("/settings")).body;
    check(
      "photo: document reports has_photo + original file name",
      doc.has_photo === true && doc.photo_name === "settings-e2e-photo.png",
      `${doc.has_photo} ${doc.photo_name}`,
    );

    await clickAria(page, "Remove profile photo");
    await waitForSectionText(page, "Profile", "Photo removed.", 15_000);
    await page.waitForFunction(
      () => !document.querySelector('img[aria-label="Profile photo preview"]'),
      { timeout: 15_000 },
    );
    const afterRemove = (await getJson("/settings")).body;
    check(
      "photo: remove restores the placeholder and clears has_photo",
      afterRemove.has_photo === false && afterRemove.photo_name === null,
    );
    const goneBlob = await fetch(`${API}/settings/profile/photo`);
    check("photo: blob route answers 404 once unset", goneBlob.status === 404, String(goneBlob.status));
    await goneBlob.arrayBuffer();

    // ------------------------------------------------ PART 2 appearance/theme
    await clickAria(page, "Theme dark");
    await setInputValue(page, 'input[aria-label="Appearance custom theme"]', "Ocean");
    await clickAria(page, "Save appearance");
    await waitForSectionText(page, "Appearance", "Saved.", 10_000);
    check("theme: dark applies .dark to <html> immediately after save", await htmlHasDark(page));
    doc = (await getJson("/settings")).body;
    check(
      "theme: server stores dark + the inactive custom theme name",
      doc.sections.appearance.theme === "dark" && doc.sections.appearance.custom_theme === "Ocean",
      JSON.stringify(doc.sections.appearance),
    );
    await page.reload({ waitUntil: "networkidle2", timeout: 60_000 });
    await waitForText(page, "Settings & Preferences", 30_000);
    await page.waitForFunction(() => document.documentElement.classList.contains("dark"), {
      timeout: 15_000,
    });
    check("theme: dark survives a reload via the root ThemeEffect bootstrap", true);
    check(
      "theme: reload restores the saved field values",
      (await inputValue(page, 'input[aria-label="Profile name"]')) === PROFILE.name &&
        (await inputValue(page, 'input[aria-label="Appearance custom theme"]')) === "Ocean",
    );

    await clickAria(page, "Theme light");
    await clickAria(page, "Save appearance");
    await waitForSectionText(page, "Appearance", "Saved.", 10_000);
    check("theme: switching to light removes .dark", !(await htmlHasDark(page)));

    // ------------------------------------------------ PART 3 academic defaults
    await setInputValue(page, 'input[aria-label="Academic default session"]', "2025-26");
    await setInputValue(page, 'input[aria-label="Academic default department"]', "Computer Science");
    await setInputValue(page, 'input[aria-label="Academic default programme"]', "B.Sc. (Hons.)");
    await setInputValue(page, 'input[aria-label="Academic default semester"]', "Semester 3");
    await setInputValue(page, 'select[aria-label="Academic timezone"]', "Asia/Kolkata");
    await setInputValue(page, 'select[aria-label="Academic date format"]', "dd-mm-yyyy");
    await clickAria(page, "Save academic defaults");
    await waitForSectionText(page, "Academic defaults", "Saved.", 10_000);
    doc = (await getJson("/settings")).body;
    check(
      "academic: defaults round-trip to the API",
      doc.sections.academic.default_session === "2025-26" &&
        doc.sections.academic.default_department === "Computer Science" &&
        doc.sections.academic.default_programme === "B.Sc. (Hons.)" &&
        doc.sections.academic.default_semester === "Semester 3" &&
        doc.sections.academic.default_timezone === "Asia/Kolkata" &&
        doc.sections.academic.date_format === "dd-mm-yyyy",
      JSON.stringify(doc.sections.academic),
    );

    // ------------------------------------------------ PART 4 notifications
    await clickAria(page, "Notifications enabled");
    await setInputValue(page, 'select[aria-label="Default reminder"]', "one_day_before");
    await setInputValue(page, 'select[aria-label="Default priority"]', "high");
    await setInputValue(page, 'select[aria-label="Default calendar view"]', "week");
    await clickAria(page, "Default calendar source Events");
    await clickAria(page, "Default calendar source Personal");
    await clickAria(page, "Save notification preferences");
    await waitForSectionText(page, "Notification preferences", "Saved.", 10_000);
    doc = (await getJson("/settings")).body;
    check(
      "notifications: preferences round-trip to the API",
      doc.sections.notifications.enabled === false &&
        doc.sections.notifications.reminder_default === "one_day_before" &&
        doc.sections.notifications.priority_default === "high" &&
        doc.sections.notifications.calendar_default_view === "week" &&
        JSON.stringify(doc.sections.notifications.calendar_default_sources) ===
          JSON.stringify(["events", "personal"]),
      JSON.stringify(doc.sections.notifications),
    );

    // ------------------------------------------------ PART 5 dashboard prefs
    await setInputValue(page, 'select[aria-label="Default landing page"]', "/reports");
    await setInputValue(page, 'select[aria-label="Default dashboard view"]', "compact");
    await clickAria(page, "Favorite module Objects");
    await clickAria(page, "Favorite module Finance");
    await clickAria(page, "Widget Reminders"); // uncheck (default visible)
    await clickAria(page, "Widget Tasks"); // uncheck
    await clickAria(page, "Save dashboard preferences");
    await waitForSectionText(page, "Dashboard preferences", "Saved.", 10_000);
    doc = (await getJson("/settings")).body;
    check(
      "dashboard: preferences round-trip to the API",
      doc.sections.dashboard.default_landing_page === "/reports" &&
        doc.sections.dashboard.default_view === "compact" &&
        JSON.stringify(doc.sections.dashboard.favorite_modules) ===
          JSON.stringify(["objects", "finance"]) &&
        doc.sections.dashboard.widget_visibility.reminders === false &&
        doc.sections.dashboard.widget_visibility.tasks === false &&
        (doc.sections.dashboard.widget_visibility.calendar ?? true) === true,
      JSON.stringify(doc.sections.dashboard),
    );

    // ------------------------------------------------ PART 7 search prefs
    await setInputValue(page, 'select[aria-label="Default search scope"]', "documents");
    await setInputValue(page, 'input[aria-label="Recent searches limit"]', "25");
    await setInputValue(page, 'textarea[aria-label="Saved filters"]', "[1,2]");
    await clickAria(page, "Save search preferences");
    await waitForSectionText(page, "Search preferences", "must be a JSON object", 10_000);
    check("search: non-object saved filters are blocked client-side", true);
    await setInputValue(page, 'textarea[aria-label="Saved filters"]', JSON.stringify(SAVED_FILTERS, null, 2));
    await clickAria(page, "Save search preferences");
    await waitForSectionText(page, "Search preferences", "Saved.", 10_000);
    doc = (await getJson("/settings")).body;
    check(
      "search: preferences round-trip to the API",
      doc.sections.search.default_scope === "documents" &&
        doc.sections.search.recent_searches_limit === 25 &&
        JSON.stringify(doc.sections.search.saved_filters) === JSON.stringify(SAVED_FILTERS),
      JSON.stringify(doc.sections.search),
    );

    // ------------------------------------------------ PART 8 privacy
    await clickAria(page, "Remember last module"); // off
    await clickAria(page, "Reduce motion"); // on
    await setInputValue(page, 'select[aria-label="Session page size"]', "50");
    await clickAria(page, "Save privacy preferences");
    await waitForSectionText(page, "Privacy", "Saved.", 10_000);
    doc = (await getJson("/settings")).body;
    check(
      "privacy: preferences round-trip to the API",
      doc.sections.privacy.remember_last_module === false &&
        doc.sections.privacy.reduce_motion === true &&
        doc.sections.privacy.session_filter_memory === true &&
        doc.sections.privacy.session_page_size === 50,
      JSON.stringify(doc.sections.privacy),
    );

    // ------------------------------------------------ PART 10 AI (stored-inactive)
    check(
      "ai: section is marketed as stored-for-future (inactive badge)",
      await page.evaluate(
        () =>
          document
            .querySelector('section[aria-label="AI & personalization"]')
            ?.textContent.includes("Stored for future use — inactive") ?? false,
      ),
    );
    await setInputValue(page, 'input[aria-label="Preferred writing style"]', "concise and formal");
    await setInputValue(page, 'select[aria-label="Preferred report format"]', "pdf");
    await setInputValue(page, 'select[aria-label="Preferred dashboard layout"]', "wide");
    await clickAria(page, "Save AI preferences");
    await waitForSectionText(page, "AI & personalization", "Saved.", 10_000);
    doc = (await getJson("/settings")).body;
    check(
      "ai: preferences round-trip to the API",
      doc.sections.ai.preferred_writing_style === "concise and formal" &&
        doc.sections.ai.preferred_report_format === "pdf" &&
        doc.sections.ai.preferred_dashboard_layout === "wide",
      JSON.stringify(doc.sections.ai),
    );

    // ------------------------------------------------ PART 6 backup & restore
    const exported = (await getJson("/settings/export")).body;
    check(
      "backup: export contract (version/app/8 sections, photo omitted)",
      exported.version === 1 &&
        typeof exported.app === "string" &&
        exported.app.length > 0 &&
        Object.keys(exported.sections).length === 8 &&
        exported.sections.profile.name === PROFILE.name &&
        !JSON.stringify(exported).includes("_photo") &&
        !JSON.stringify(exported).includes("settings-e2e-photo"),
    );

    fs.writeFileSync(
      IMPORT_PATH,
      JSON.stringify(
        {
          version: 1,
          sections: {
            profile: { name: IMPORT_NAME },
            appearance: { theme: "system" },
          },
        },
        null,
        2,
      ),
    );
    armDialog(page);
    const importInput = await page.$('input[aria-label="Import settings file"]');
    check("backup: import file input present", Boolean(importInput));
    await importInput.uploadFile(IMPORT_PATH);
    await waitForSectionText(page, "Backup & restore", "Imported 2 section(s)", 15_000);
    doc = (await getJson("/settings")).body;
    check(
      "backup: import merges only the provided keys",
      doc.sections.profile.name === IMPORT_NAME &&
        doc.sections.profile.email === PROFILE.email && // untouched key kept
        doc.sections.appearance.theme === "system" &&
        doc.sections.search.recent_searches_limit === 25, // untouched section kept
      JSON.stringify({ name: doc.sections.profile.name, email: doc.sections.profile.email }),
    );
    check(
      "backup: imported values hydrate the UI without a reload",
      (await inputValue(page, 'input[aria-label="Profile name"]')) === IMPORT_NAME &&
        (await ariaChecked(page, "Theme system")) === "true",
    );

    armDialog(page);
    await clickAria(page, "Reset preferences");
    await waitForSectionText(page, "Backup & restore", "factory defaults", 15_000);
    doc = (await getJson("/settings")).body;
    check(
      "backup: reset restores factory defaults everywhere",
      doc.sections.profile.name === "" &&
        doc.sections.appearance.theme === "system" &&
        doc.sections.academic.date_format === "yyyy-mm-dd" &&
        doc.sections.notifications.enabled === true &&
        doc.sections.search.recent_searches_limit === 10 &&
        doc.sections.privacy.session_page_size === 20 &&
        doc.sections.dashboard.favorite_modules.length === 0,
      JSON.stringify({ name: doc.sections.profile.name, theme: doc.sections.appearance.theme }),
    );
    check(
      "backup: reset hydrates the UI back to defaults",
      (await inputValue(page, 'input[aria-label="Profile name"]')) === "" &&
        (await isChecked(page, "Notifications enabled")) === true,
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
      await page.screenshot({ path: "/tmp/settings-failure.png", fullPage: true });
      fs.writeFileSync("/tmp/settings-failure.txt", await page.content());
    } catch {
      /* ignore */
    }
  } finally {
    await browser.close();
    // Leave the canonical database as found: factory defaults, no photo.
    await fetch(`${API}/settings/profile/photo`, { method: "DELETE" }).catch(() => {});
    await postJson("/settings/reset", {});
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

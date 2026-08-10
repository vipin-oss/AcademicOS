# AcademicOS browser E2E harness (Puppeteer)

The `*-e2e.mjs` scripts drive the **real UI** (backend + `next start`) and
verify module workflows end to end — sidebar navigation, CRUD flows, review
workflows, AI surfaces, and cleanliness gates (zero failed API calls, zero
console errors).

## Prerequisites

- Backend running: `cd backend && uvicorn app.main:app --port 8000`
  (PostgreSQL or SQLite; see `INSTALL.md`)
- Frontend built and running: `cd frontend && npm run build && npm start`
- A seeded database — each script seeds its own dated world through the
  module APIs, but `backend/seed_regression.py` provides the base corpus
  used by the Objects/Documents/Publications suites.

## Running

```bash
cd frontend
npm run test:e2e            # runs every *-e2e.mjs against localhost:3000
node e2e/chat-e2e.mjs       # run a single suite
```

`puppeteer` is a declared devDependency; `npm ci` installs it and its
bundled Chromium. These suites are NOT part of `npm test` (unit tests) and
are not required for the production build — they are the browser-level
verification layer, run on demand or in CI when a browser is available.

# Frontend — AcademicOS (Next.js 14, App Router)

The AcademicOS web client. Connects to the FastAPI backend at
`http://127.0.0.1:8000/api/v1` by default (override with
`NEXT_PUBLIC_API_URL` in `.env.local` — see `.env.example`).

## Quickstart

```powershell
npm install
npm run dev        # http://127.0.0.1:3000
```

Register an account on `/register`, then sign in. Protected routes are
guarded by middleware (session cookie) and the client-side session
provider; expired access tokens are refreshed automatically once via the
refresh token, then the session signs out.

## Modules

| Route | Module |
|---|---|
| `/` | Dashboard |
| `/assistant` | AI Assistant (chat + memory/review/eval Labs) |
| `/objects` `/objects/[id]` | Objects (incl. Relationships graph + ACL panel) |
| `/documents` | Documents |
| `/intake` | Intake |
| `/publications` | Publications |
| `/students` | Students |
| `/teaching` | Teaching |
| `/research` | Research |
| `/faculty` | Faculty |
| `/committees` | Committees |
| `/finance` | Finance |
| `/events` | Events |
| `/productivity` | Productivity (tasks, reminders, calendar, notifications) |
| `/reports` | Reports |
| `/search` | Global search |
| `/settings` | Settings |
| `/login` `/register` `/forgot-password` `/reset-password` | Authentication |

## Conventions

- Feature components live in `src/components/features/<screen>/`; shared
  layout in `src/components/layout/`; API clients in `src/lib/api/`.
- Auth tokens are managed in `src/lib/auth/` (localStorage + session
  cookie) and attached automatically by the API client.
- Hooks in `src/hooks/`; shared types in `src/types/`.
- Tests: `npx vitest run` (unit) and `frontend/tests/*.e2e.mjs`
  (scripted manual/regression flows).

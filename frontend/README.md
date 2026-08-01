# Frontend — AcademicOS (Next.js)

Folder skeleton only. No business logic or configuration yet.

## Screen / Module Map

Each screen from the UI Specification maps to a folder under
`src/app/(main)/` (route) and `src/components/features/<screen>/` (components):

| Folder | UI Spec screen |
|---|---|
| `dashboard` | Dashboard (AI Briefing) |
| `documents` | Document Library / Viewer |
| `teaching` | Teaching |
| `research` | Research |
| `publications` | Publications |
| `projects` | Projects |
| `administration` | Administration |
| `students` | Students |
| `calendar` | Calendar |
| `ai-chat` | AI Chat (Screen 9) |
| `settings` | Settings |
| `notifications` | Notifications |
| `search` | Search (Screen 12) |
| `auth` | Auth (sign-in / sign-up) |

## Conventions (to be enforced when code is added)

- **ShadCN** primitives live in `src/components/ui/` (added by the ShadCN CLI).
- **State** is kept in `src/stores/`; server state goes through `src/lib/api/`.
- **Auth** tokens (JWT) are managed in `src/lib/auth/` and attached via the API client.
- **Storage adapters** (local / Google Drive / OneDrive) live in `src/lib/storage/`.
- Every `features/<screen>` folder owns its components, hooks, and local types.

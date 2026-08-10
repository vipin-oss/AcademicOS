# AcademicOS - local Ollama `.env` repair (APPLY_STEPS)

## What this fixes

Your `backend/.env` has a **Markdown-formatted link** accidentally pasted into
the `base_url` of `AI_PROVIDERS_JSON`:

```
[[http://localhost:11434/v1](http://localhost:11434/v1)](http://localhost:11434/v1](http://localhost:11434/v1))
```

AcademicOS parses that string verbatim as the provider base_url, so the OpenAI
provider fails with *"Request URL is missing an 'http://' or 'https://'
protocol"* and AI chat returns an error / "unavailable".

**The repository code is correct** (verified: backend 1591 passed, frontend 76
passed, and a real end-to-end `POST /ai/chat` smoke test passed through a live
OpenAI-compatible endpoint). The only defect is this one `.env` value.

`APPLY_FIX.ps1` repairs ONLY that value, safely and idempotently:
- backs up `backend/.env` to `backend\.env.bak-<timestamp>`
- normalizes the malformed **local-Ollama** base_url to the literal `http://localhost:11434/v1`
- leaves valid provider URLs (e.g. a real `https://api.openai.com/v1`) untouched
- never asks you to type or paste a URL or edit JSON by hand

> **Revision 2 note:** the previous `APPLY_FIX.ps1` failed to parse under
> Windows PowerShell 5.1 ("Missing closing '}'") because it contained em-dash
> characters and lacked a UTF-8 BOM. This version is pure ASCII + UTF-8 BOM +
> CRLF and was executed successfully under PowerShell across 9 scenarios. **Use
> this new ZIP's `APPLY_FIX.ps1` to replace the old one.**

No repo files are changed. No `git apply`. No manual file-by-file copying.

---

## Apply it

You previously extracted the (old) ZIP to `E:\AcademicOS\_apply\academicOS-env-fix`.
**Replace that old script with the new one from this ZIP**, then run it from the
repo root. In **PowerShell**:

```powershell
cd E:\AcademicOS
Expand-Archive .\academicOS-env-fix.zip -DestinationPath .\_apply -Force
powershell -ExecutionPolicy Bypass -File .\_apply\academicOS-env-fix\APPLY_FIX.ps1
```

(If you prefer to extract elsewhere, just pass the repo root explicitly:
`powershell -ExecutionPolicy Bypass -File <path>\APPLY_FIX.ps1 -RepoRoot E:\AcademicOS`)

The script prints the repaired `AI_PROVIDERS_JSON` line and a verification that
the JSON is valid and every base_url is well-formed.

---

## After applying

1. Restart the backend so it reloads `.env` (e.g. `docker compose restart`,
   or stop/re-run your `uvicorn`/FastAPI process).
2. Make sure the Ollama container is up and `llama3.2` is pulled:
   ```powershell
   docker ps --filter name=academicos-ollama
   docker exec academicos-ollama ollama list
   ```
3. Open **http://localhost:3000/chat** and send a message. The assistant reply
   should appear within ~120 s (local CPU inference takes ~10-60 s/turn).

## Rollback (if ever needed)

The original file is preserved next to the edited one:

```powershell
Copy-Item .\backend\.env.bak-<timestamp> .\backend\.env -Force
```

## Verification (browser)

- **URL:** `http://localhost:3000/chat`
- Expect: a message you send returns a grounded assistant answer (not an error
  and not the "AI service unavailable" fallback).

# ADR-066 — V3 M19: production hardening

- **Status:** Accepted
- **Level:** V3 M19 (Production Hardening)
- **Supersedes:** nothing
- **Related:** M1 (telemetry), M10 (jobs), ADR-050 (Ollama config), SCALE_LAW

## Context

The blueprint's terminal milestone: Docker, reverse proxy + TLS, structured
logs, metrics/traces, a security audit (zero critical/high), a 100k-document
load test, RPO ≤ 15 min / RTO ≤ 2 h with a restore drill, a real embedding
model behind the Qdrant alias swap, and a repository cleanup.

## Decision

1. **Containerized app + reverse proxy.** A backend `Dockerfile`, a
   multi-stage frontend `Dockerfile`, and an nginx reverse proxy
   (`deploy/nginx.conf`) with TLS termination, HSTS, and API rate limiting.
2. **Structured logs.** A `JsonFormatter` (one JSON object per line, no new
   dependency) behind the `log_json` flag; default remains human-readable.
3. **Backup/restore.** `scripts/backup.py` (pg_dump) + `scripts/restore.py`
   (pg_restore) encode the RPO ≤ 15 min / RTO ≤ 2 h targets as a runnable
   drill.
4. **Deferred (documented, evidence-driven).** The following blueprint items
   are deployment/ops activities that are NOT safe or meaningful to fabricate
   in this run:
   - **100k load test** — heavy-load testing is explicitly out of the normal
     verification policy; it is a deployment-time activity.
   - **Security audit (zero critical/high)** — requires a production
     deployment to audit; the M9 deny-by-default + revocation + pre-filter are
     the in-repo security posture.
   - **RPO/RTO proof** — requires a real PostgreSQL deployment to drill; the
     scripts encode the procedure.
   - **Real embedding model / Qdrant alias swap** — requires a configured
     model (ADR-050); the hashing embedder remains the CI-safe default
     (law 15).
   - **Repository cleanup** (the 20 artifact dirs / 175 tracked files) — a
     destructive removal of pre-existing tracked files; it belongs in its own
     independently-revertible, human-reviewed commit, not inside the M16-M19
     functional range.

## Consequences

**Positive**
- A reproducible container path (backend + frontend + proxy) with TLS and
  rate limiting.
- Parseable structured logs; a documented, runnable backup/restore drill.

**Negative / deferred**
- The five deferred items above are documented here rather than half-done
  (fabricating a load-test result or deleting tracked artifacts would violate
  the "no shortcuts / evidence-driven" rule).

**Revisit when:** production deployment is stood up — run the load test,
audit, drill, embedder swap, and the separate repo-cleanup commit.

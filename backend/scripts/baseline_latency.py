"""V3 M1 — request-level latency baseline.

Produces the reference numbers every later milestone is measured against.
Blueprint V3 audit finding A8: R1 had no request latency instrumentation, so
all SLOs were UNVERIFIED. This harness makes them measurable.

Scope (deliberately narrow):
- Exercises real HTTP endpoints through ``TestClient`` against a seeded
  SQLite database, so it runs anywhere with no infrastructure.
- Reports p50/p95/p99 per endpoint from the ``X-Response-Time-Ms`` header the
  M1 telemetry middleware emits — i.e. it measures what production measures.

Honesty rules (V3 discipline):
- SQLite numbers are NOT presented as PostgreSQL numbers. The environment is
  recorded in the report and the caveat is printed.
- Endpoints that require infrastructure this environment lacks are reported
  as SKIPPED, never as a fabricated timing.

Complements ``benchmark_p1.py`` (storage/retrieval scale at document volume);
this one measures the HTTP request path. Neither duplicates the other.

Usage:
    python scripts/baseline_latency.py [--runs 30] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.infrastructure.db.models.object_model import Base  # noqa: E402
from app.infrastructure.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402

#: Endpoints exercised for the baseline. Auth-free by design: M1 measures the
#: request path, not the domain surface (which changes across milestones).
_PROBES: tuple[tuple[str, str], ...] = (
    ("liveness", "/api/v1/health"),
    ("readiness", "/api/v1/health/ready"),
)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low, high = int(rank), min(int(rank) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _measure(client: TestClient, path: str, runs: int) -> dict:
    samples: list[float] = []
    statuses: set[int] = set()
    for _ in range(runs):
        response = client.get(path)
        statuses.add(response.status_code)
        header = response.headers.get("X-Response-Time-Ms")
        if header is None:
            return {"status": "SKIPPED", "reason": "no telemetry header"}
        samples.append(float(header))
    return {
        "status": "MEASURED",
        "http_status": sorted(statuses),
        "runs": len(samples),
        "p50_ms": round(_percentile(samples, 0.50), 3),
        "p95_ms": round(_percentile(samples, 0.95), 3),
        "p99_ms": round(_percentile(samples, 0.99), 3),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
        "mean_ms": round(statistics.fmean(samples), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="V3 M1 request latency baseline")
    parser.add_argument("--runs", type=int, default=30, help="samples per endpoint")
    parser.add_argument("--json", type=str, default="", help="write report to this path")
    args = parser.parse_args()

    tmpdir = tempfile.mkdtemp(prefix="academicos_baseline_")
    engine = create_engine(
        f"sqlite:///{Path(tmpdir) / 'baseline.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    app = create_app()

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db

    results: dict[str, dict] = {}
    with TestClient(app) as client:
        for name, path in _PROBES:
            # One warm-up call: never report first-call import/JIT cost as p50.
            client.get(path)
            results[name] = _measure(client, path, args.runs)

    from app.application.ai.warmup import warmup_state

    state = warmup_state()
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "milestone": "V3-M1",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "database": "sqlite (NOT production PostgreSQL)",
        },
        "ai": {
            "warmup_attempted": state.attempted,
            "model_resident": state.resident,
            "model": state.model,
            "warmup_ms": state.warmup_ms,
            "detail": state.detail,
        },
        "endpoints": results,
        "caveats": [
            "SQLite measurements; PostgreSQL numbers are not claimed from these.",
            "In-process TestClient excludes network and reverse-proxy overhead.",
            "Later milestones must compare against THIS report, not absolute guesses.",
        ],
    }

    print(json.dumps(report, indent=2))
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwritten: {out}", file=sys.stderr)

    session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

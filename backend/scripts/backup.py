"""PostgreSQL backup (V3 M19, ADR-066 — RPO <= 15 min target).

Wraps ``pg_dump`` for a consistent logical backup. Run from a scheduler at the
RPO cadence. The restore drill (restore.py) verifies recoverability.

Usage:
    DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/academicos \
    python scripts/backup.py --out ./backups
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def _pg_env(database_url: str) -> dict[str, str]:
    parsed = urlparse(database_url.replace("postgresql+psycopg2://", "postgresql://"))
    env = {
        "PGHOST": parsed.hostname or "localhost",
        "PGPORT": str(parsed.port or 5432),
        "PGUSER": parsed.username or "postgres",
        "PGPASSWORD": parsed.password or "",
        "PGDATABASE": parsed.path.lstrip("/") or "academicos",
    }
    return env


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="./backups")
    args = parser.parse_args()

    database_url = __import__("os").environ.get("DATABASE_URL", "")
    if not database_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    dump_path = out_dir / f"academicos-{stamp}.dump"

    cmd = ["pg_dump", "--format=custom", "--file", str(dump_path)]
    env = {**__import__("os").environ, **_pg_env(database_url)}
    subprocess.run(cmd, check=True, env=env)
    print(f"Backup written: {dump_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

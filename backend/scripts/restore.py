"""PostgreSQL restore drill (V3 M19, ADR-066 — RTO <= 2 h target).

Restores a backup produced by backup.py into a fresh/empty database. This is
the "restore with proof" step: run it on a scratch database on schedule to
prove recoverability.

Usage:
    DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/academicos_restore \
    python scripts/restore.py --dump ./backups/academicos-2026....dump
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def _pg_env(database_url: str) -> dict[str, str]:
    parsed = urlparse(database_url.replace("postgresql+psycopg2://", "postgresql://"))
    return {
        "PGHOST": parsed.hostname or "localhost",
        "PGPORT": str(parsed.port or 5432),
        "PGUSER": parsed.username or "postgres",
        "PGPASSWORD": parsed.password or "",
        "PGDATABASE": parsed.path.lstrip("/") or "academicos",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", required=True)
    args = parser.parse_args()

    database_url = __import__("os").environ.get("DATABASE_URL", "")
    if not database_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 2

    dump = Path(args.dump)
    if not dump.exists():
        print(f"Dump not found: {dump}", file=sys.stderr)
        return 2

    env = {**__import__("os").environ, **_pg_env(database_url)}
    subprocess.run(["pg_restore", "--clean", "--if-exists", "--dbname", env["PGDATABASE"], str(dump)],
                   check=True, env=env)
    print(f"Restored {dump} into {env['PGDATABASE']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

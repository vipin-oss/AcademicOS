"""Outbox relay process (V3 M10, ADR-057).

A standalone process that drains the durable outbox into the derived search
projection on an interval — the "continuously-running relay" the blueprint
references (ADR-055 defers the read-time-drain retirement to this process).
Runs forever; each drain is idempotent and bounded.

Usage (from backend/):
    python scripts/relay.py
"""

from __future__ import annotations

import time

from app.core.config import settings
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
from app.infrastructure.search.index_applier import SearchIndexApplier


def main() -> None:
    interval = settings.relay_interval_seconds
    while True:
        try:
            db = SessionLocal()
            try:
                SearchIndexApplier(
                    db, vector_repository=None, embedder=HashingEmbedder()
                ).apply_pending()
            finally:
                db.close()
        except KeyboardInterrupt:
            break
        except Exception:  # noqa: BLE001 - relay must survive transient errors
            pass
        time.sleep(interval)


if __name__ == "__main__":
    main()

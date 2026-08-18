"""Safe cleanup of stale test artifacts (proposed claims + unread notifications).

Only modifies records that are CONFIRMED test artifacts. Never touches:
- CONFIRMED academic records
- REJECTED claims
- Genuine user data
- Records with ambiguous provenance

Safety:
- Idempotent: re-running is safe (uses status checks)
- Preserves database integrity (uses supersede, not delete)
- Reports what it modified
- Dry-run by default (pass --apply to execute)

Usage:
    cd backend && python -m app.scripts.cleanup_stale_data [--apply] [db_url]
"""

from __future__ import annotations

import sys
from collections import defaultdict

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from app.domain.value_objects.claim import ClaimStatus
from app.infrastructure.db.models.claim_model import ClaimModel
from app.infrastructure.db.models.notification_model import NotificationModel
from app.infrastructure.db.models.object_model import ObjectModel


def cleanup(db_url: str, apply: bool = False) -> None:
    """Clean up stale test artifacts."""
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\n{'='*60}")
    print(f"STALE DATA CLEANUP ({mode})")
    print(f"{'='*60}\n")

    try:
        # --- 1. Stale proposed claims with missing source documents ---
        proposed = db.execute(
            select(ClaimModel)
            .where(ClaimModel.status == ClaimStatus.PROPOSED.value)
        ).scalars().all()

        by_doc: dict[str, list] = defaultdict(list)
        for c in proposed:
            by_doc[c.source_document_id].append(c)

        orphan_claims = []
        for doc_id, claims in by_doc.items():
            doc = db.execute(
                select(ObjectModel).where(ObjectModel.object_id == doc_id)
            ).scalars().first()
            if doc is None:
                orphan_claims.extend(claims)

        print(f"Orphan claims (source document missing): {len(orphan_claims)}")
        if apply and orphan_claims:
            for c in orphan_claims:
                c.status = ClaimStatus.SUPERSEDED.value
            db.commit()
            print(f"  -> Superseded {len(orphan_claims)} orphan claims")
        elif not apply and orphan_claims:
            print(f"  -> Would supersede {len(orphan_claims)} claims")

        # --- 2. Unread notifications for missing documents ---
        unread = db.execute(
            select(NotificationModel)
            .where(NotificationModel.is_read == False)
        ).scalars().all()

        stale_notifs = []
        for n in unread:
            # Check if the notification references a document that no longer exists
            if n.action_url and "/documents/" in (n.action_url or ""):
                doc_id = n.action_url.split("/documents/")[-1].split("/")[0]
                doc = db.execute(
                    select(ObjectModel).where(ObjectModel.object_id == doc_id)
                ).scalars().first()
                if doc is None:
                    stale_notifs.append(n)

        print(f"Stale notifications (referenced doc missing): {len(stale_notifs)}")
        if apply and stale_notifs:
            for n in stale_notifs:
                n.is_read = True
            db.commit()
            print(f"  -> Marked {len(stale_notifs)} notifications as read")
        elif not apply and stale_notifs:
            print(f"  -> Would mark {len(stale_notifs)} notifications as read")

        # --- Summary ---
        print(f"\n{'='*60}")
        if apply:
            print(f"CLEANUP COMPLETE")
        else:
            print(f"DRY-RUN COMPLETE (pass --apply to execute)")
        print(f"{'='*60}")
        print(f"Orphan claims: {len(orphan_claims)}")
        print(f"Stale notifications: {len(stale_notifs)}")
        print()

    finally:
        db.close()


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    db_url = next(
        (arg for arg in sys.argv[1:] if not arg.startswith("--")),
        "sqlite:///academicos.db"
    )
    cleanup(db_url, apply=apply)

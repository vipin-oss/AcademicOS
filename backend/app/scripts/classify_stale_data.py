"""Dry-run classification of stale proposed claims and unread notifications.

Identifies records that are clearly test artifacts vs potentially valid
academic data. Never modifies anything — read-only analysis.

Usage:
    cd backend && python -m app.scripts.classify_stale_data
"""

from __future__ import annotations

import sys
from collections import defaultdict

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.domain.value_objects.claim import ClaimStatus
from app.infrastructure.db.models.claim_model import ClaimModel
from app.infrastructure.db.models.notification_model import NotificationModel
from app.infrastructure.db.models.object_model import ObjectModel


def classify(db_url: str) -> None:
    """Classify stale proposed claims and unread notifications."""
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # --- Stale proposed claims ---
        proposed = db.execute(
            select(ClaimModel)
            .where(ClaimModel.status == ClaimStatus.PROPOSED.value)
            .order_by(ClaimModel.created_at)
        ).scalars().all()

        print(f"\n{'='*60}")
        print(f"STALE PROPOSED CLAIMS: {len(proposed)}")
        print(f"{'='*60}\n")

        # Group by source document
        by_doc: dict[str, list] = defaultdict(list)
        for c in proposed:
            by_doc[c.source_document_id].append(c)

        test_artifacts = []
        potentially_valid = []

        for doc_id, claims in sorted(by_doc.items()):
            # Check if the source document still exists
            doc = db.execute(
                select(ObjectModel).where(ObjectModel.object_id == doc_id)
            ).scalars().first()

            is_test = False
            reasons = []

            # Heuristic 1: document doesn't exist
            if doc is None:
                is_test = True
                reasons.append("source document missing")

            # Heuristic 2: all claims have very similar created_at timestamps
            # (batch-created in a test run)
            timestamps = [c.created_at for c in claims if c.created_at]
            if len(timestamps) >= 3:
                from datetime import datetime, timedelta
                ts_sorted = sorted(timestamps)
                span = (ts_sorted[-1] - ts_sorted[0]).total_seconds()
                if span < 5:  # all created within 5 seconds
                    is_test = True
                    reasons.append(f"batch-created ({span:.1f}s span)")

            # Heuristic 3: suspicious predicate patterns
            pred_ids = {c.predicate_id for c in claims}
            if len(pred_ids) == 1 and len(claims) > 3:
                is_test = True
                reasons.append(f"many duplicate claims for same predicate")

            if is_test:
                test_artifacts.append((doc_id, claims, reasons))
            else:
                potentially_valid.append((doc_id, claims))

        print(f"Test artifacts: {len(test_artifacts)} documents, "
              f"{sum(len(c) for _, c, _ in test_artifacts)} claims")
        for doc_id, claims, reasons in test_artifacts[:5]:
            print(f"  {doc_id}: {len(claims)} claims ({', '.join(reasons)})")
        if len(test_artifacts) > 5:
            print(f"  ... and {len(test_artifacts) - 5} more")

        print(f"\nPotentially valid: {len(potentially_valid)} documents, "
              f"{sum(len(c) for _, c in potentially_valid)} claims")
        for doc_id, claims in potentially_valid[:5]:
            preds = {c.predicate_id for c in claims}
            print(f"  {doc_id}: {len(claims)} claims ({', '.join(sorted(preds)[:3])}...)")
        if len(potentially_valid) > 5:
            print(f"  ... and {len(potentially_valid) - 5} more")

        # --- Unread notifications ---
        unread = db.execute(
            select(NotificationModel)
            .where(NotificationModel.is_read == False)
            .order_by(NotificationModel.created_at)
        ).scalars().all()

        print(f"\n{'='*60}")
        print(f"UNREAD NOTIFICATIONS: {len(unread)}")
        print(f"{'='*60}\n")

        # Group by user
        by_user: dict[str, list] = defaultdict(list)
        for n in unread:
            by_user[n.user_id].append(n)

        for user_id, notifs in sorted(by_user.items()):
            print(f"  User {user_id}: {len(notifs)} unread")
            for n in notifs[:3]:
                print(f"    - {n.notification_type}: {n.title[:50]}...")
            if len(notifs) > 3:
                print(f"    ... and {len(notifs) - 3} more")

        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"{'='*60}")
        print(f"Stale proposed claims: {len(proposed)}")
        print(f"  Test artifacts (safe to clean): {sum(len(c) for _, c, _ in test_artifacts)}")
        print(f"  Potentially valid (leave alone): {sum(len(c) for _, c in potentially_valid)}")
        print(f"Unread notifications: {len(unread)}")
        print()

    finally:
        db.close()


if __name__ == "__main__":
    db_url = sys.argv[1] if len(sys.argv) > 1 else "sqlite:///academicos.db"
    classify(db_url)

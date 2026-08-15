"""SQL implementation of the saved-view store (V3 M13, ADR-060)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.application.ports.saved_view_store import SavedViewRecord, SavedViewStore
from app.infrastructure.db.models.saved_view_model import SavedViewModel


class SQLSavedViewStore(SavedViewStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, view: SavedViewRecord) -> SavedViewRecord:
        existing = self._session.execute(
            select(SavedViewModel).where(SavedViewModel.id == view.id)
        ).scalars().first()
        if existing is not None:
            return view
        self._session.add(
            SavedViewModel(
                id=view.id,
                name=view.name,
                definition=view.definition,
                owner_user_id=view.owner_user_id,
                created_at=view.created_at,
            )
        )
        return view

    def get(self, view_id: str) -> SavedViewRecord | None:
        row = self._session.execute(
            select(SavedViewModel).where(SavedViewModel.id == view_id)
        ).scalars().first()
        return _from_model(row) if row else None

    def list_for_owner(self, owner_user_id: str) -> list[SavedViewRecord]:
        rows = self._session.execute(
            select(SavedViewModel)
            .where(SavedViewModel.owner_user_id == owner_user_id)
            .order_by(SavedViewModel.created_at.desc())
        ).scalars().all()
        return [_from_model(r) for r in rows]

    def delete(self, view_id: str) -> None:
        self._session.execute(delete(SavedViewModel).where(SavedViewModel.id == view_id))


def _from_model(row: SavedViewModel) -> SavedViewRecord:
    return SavedViewRecord(
        id=row.id,
        name=row.name,
        definition=row.definition or {},
        owner_user_id=row.owner_user_id,
        created_at=row.created_at,
    )

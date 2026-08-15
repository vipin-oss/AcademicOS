"""Saved ad-hoc query/export views (V3 M13, ADR-060).

Surface:
    GET    /saved-views                list my views
    POST   /saved-views                save a view definition
    GET    /saved-views/{id}           one view
    DELETE /saved-views/{id}           delete (owner or admin)
    POST   /saved-views/{id}/run       compile + run -> rows
    GET    /saved-views/{id}/export    run + export csv|xlsx

Authorization precedes aggregation: the compiled SQL's first WHERE term is the
caller's tenant, so counts/aggregates never leak across tenants. The view row
itself is owner-scoped (only the owner, or an admin, may read/run/delete it).
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.application.ports.saved_view_store import SavedViewRecord
from app.application.services.principal import principal_from_user
from app.application.services.saved_view_compiler import SavedViewCompiler
from app.application.use_cases.auth.helpers import get_roles
from app.domain.entities.object import UniversalObject
from app.infrastructure.db.session import get_db
from app.infrastructure.persistence.saved_view_store import SQLSavedViewStore

router = APIRouter(
    prefix="/saved-views",
    tags=["saved-views"],
    dependencies=[Depends(get_current_user)],
)


class SavedViewBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    definition: dict = Field(default_factory=dict)


class SavedViewOut(BaseModel):
    id: str
    name: str
    definition: dict
    created_at: str


class RunOut(BaseModel):
    columns: list[str]
    rows: list[list]


def _store(db: Session) -> SQLSavedViewStore:
    return SQLSavedViewStore(db)


def _owner_or_admin(view: SavedViewRecord, user: UniversalObject) -> bool:
    if view.owner_user_id == str(user.id):
        return True
    return "admin" in get_roles(user)


@router.get("", response_model=list[SavedViewOut])
def list_views(
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> list[SavedViewOut]:
    return [
        SavedViewOut(id=v.id, name=v.name, definition=v.definition, created_at=v.created_at)
        for v in _store(db).list_for_owner(str(user.id))
    ]


@router.post("", response_model=SavedViewOut, status_code=status.HTTP_201_CREATED)
def create_view(
    body: SavedViewBody,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> SavedViewOut:
    # Validate the definition up front so an invalid view is never stored.
    principal = principal_from_user(user)
    try:
        SavedViewCompiler.compile(body.definition, tenant_id=principal.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    record = SavedViewRecord(
        id=uuid.uuid4().hex,
        name=body.name,
        definition=body.definition,
        owner_user_id=str(user.id),
        created_at=dt.datetime.now(dt.UTC).isoformat(),
    )
    _store(db).add(record)
    db.commit()
    return SavedViewOut(id=record.id, name=record.name, definition=record.definition, created_at=record.created_at)


def _load_view(db: Session, view_id: str, user: UniversalObject) -> SavedViewRecord:
    view = _store(db).get(view_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    if not _owner_or_admin(view, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your saved view")
    return view


@router.get("/{view_id}", response_model=SavedViewOut)
def get_view(
    view_id: str,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> SavedViewOut:
    view = _load_view(db, view_id, user)
    return SavedViewOut(id=view.id, name=view.name, definition=view.definition, created_at=view.created_at)


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_view(
    view_id: str,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> Response:
    _load_view(db, view_id, user)
    _store(db).delete(view_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{view_id}/run", response_model=RunOut)
def run_view(
    view_id: str,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> RunOut:
    view = _load_view(db, view_id, user)
    principal = principal_from_user(user)
    try:
        compiled = SavedViewCompiler.compile(view.definition, tenant_id=principal.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    rows = db.execute(text(compiled.sql), compiled.params).fetchall()
    columns = list(rows[0]._mapping.keys()) if rows else (view.definition.get("columns") or [])
    return RunOut(columns=list(columns), rows=[[str(c) for c in r] for r in rows])


@router.get("/{view_id}/export")
def export_view(
    view_id: str,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> Response:
    view = _load_view(db, view_id, user)
    principal = principal_from_user(user)
    try:
        compiled = SavedViewCompiler.compile(view.definition, tenant_id=principal.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    rows = db.execute(text(compiled.sql), compiled.params).fetchall()
    columns = list(rows[0]._mapping.keys()) if rows else []
    body = _export(columns, [[str(c) for c in r] for r in rows], view.name, format)

    media_type = "text/csv; charset=utf-8" if format == "csv" else (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return Response(content=body, media_type=media_type)


def _export(columns: list[str], rows: list[list[str]], name: str, fmt: str) -> bytes:
    from app.application.dtos.reports import ReportTable, ReportView
    from app.application.use_cases.reports.exporters import (
        report_csv_bytes,
        report_xlsx_bytes,
    )

    view = ReportView(
        kind="saved",
        title=name,
        generated_at=dt.datetime.now(dt.UTC).isoformat(),
        applied_filters={},
        tables=[ReportTable(key="result", title=name, columns=tuple(columns), rows=rows)],
    )
    return report_csv_bytes(view) if fmt == "csv" else report_xlsx_bytes(view)

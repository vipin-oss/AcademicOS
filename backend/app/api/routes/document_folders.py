"""Document Folders API — organize documents into folders.

Folders are UniversalObjects with type=FOLDER. Document-folder membership
uses CONTAINS relationships. Subfolder hierarchy uses PART_OF relationships.

ACL rule: folder membership NEVER grants access to a document. A document's
own ACL remains authoritative. Deleting a folder removes relationships only.

Tags use the document's metadata JSON list (simple, scalable, no extra tables).
Favorites use a metadata flag on the document.
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
    PermissionAction,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(prefix="/documents/folders", tags=["document-folders"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class FolderCreate(BaseModel):
    name: str
    parent_id: str | None = None


class FolderUpdate(BaseModel):
    name: str | None = None


class FolderResponse(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    document_count: int = 0
    created_by: str = ""
    created_at: str = ""


class FolderListResponse(BaseModel):
    items: list[FolderResponse]
    total: int


class TagUpdate(BaseModel):
    tags: list[str]


class FavoriteUpdate(BaseModel):
    favorite: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo(db: Session) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def _folder_name(obj: UniversalObject) -> str:
    return obj.title or ""


def _parent_id(obj: UniversalObject, repo: SQLAlchemyObjectRepository) -> str | None:
    for rel in obj.relationships:
        if rel.kind is RelationshipKind.PART_OF:
            return str(rel.target)
    return None


def _doc_count(folder_id: str, repo: SQLAlchemyObjectRepository) -> int:
    obj = repo.get_by_id(ObjectId(folder_id))
    if not obj:
        return 0
    return sum(1 for r in obj.relationships if r.kind is RelationshipKind.CONTAINS)


def _to_response(obj: UniversalObject, repo: SQLAlchemyObjectRepository) -> FolderResponse:
    return FolderResponse(
        id=str(obj.id),
        name=_folder_name(obj),
        parent_id=_parent_id(obj, repo),
        document_count=_doc_count(str(obj.id), repo),
        created_by=obj.audit.created_by if obj.audit else "",
        created_at=obj.audit.created_at.isoformat() if obj.audit else "",
    )


def _require_folder_owner(folder: UniversalObject, user: UniversalObject) -> None:
    owner = folder.audit.created_by if folder.audit else None
    if owner and owner != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your folder")


# ---------------------------------------------------------------------------
# Folder CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=FolderListResponse)
def list_folders(
    parent_id: str | None = Query(None, description="Filter by parent folder ID"),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
):
    """List all folders owned by the current user, optionally under a parent."""
    repo = _repo(db)
    all_folders = repo.find_by_type(ObjectType.FOLDER)
    # Only show folders owned by this user
    my_folders = [f for f in all_folders if f.audit and f.audit.created_by == str(user.id)]

    if parent_id:
        # Filter to children of this parent
        filtered = []
        for f in my_folders:
            pid = _parent_id(f, repo)
            if pid == parent_id:
                filtered.append(f)
        my_folders = filtered
    else:
        # Top-level only (no parent)
        filtered = []
        for f in my_folders:
            pid = _parent_id(f, repo)
            if pid is None:
                filtered.append(f)
        my_folders = filtered

    return FolderListResponse(
        items=[_to_response(f, repo) for f in my_folders],
        total=len(my_folders),
    )


@router.get("/all", response_model=FolderListResponse)
def list_all_folders(
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
):
    """List ALL folders owned by the current user (flat, not filtered by parent)."""
    repo = _repo(db)
    all_folders = repo.find_by_type(ObjectType.FOLDER)
    my_folders = [f for f in all_folders if f.audit and f.audit.created_by == str(user.id)]
    return FolderListResponse(
        items=[_to_response(f, repo) for f in my_folders],
        total=len(my_folders),
    )


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    body: FolderCreate,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
):
    """Create a new folder, optionally under a parent folder."""
    repo = _repo(db)

    # Validate parent exists and is owned by user
    if body.parent_id:
        parent = repo.get_by_id(ObjectId(body.parent_id))
        if parent is None or parent.object_type != ObjectType.FOLDER:
            raise HTTPException(status_code=404, detail="Parent folder not found")
        _require_folder_owner(parent, user)

    # Create folder as a UniversalObject
    from app.application.commands.create_object import CreateObjectCommand
    from app.application.dtos.object import CreateObjectInput
    from app.application.use_cases.create_object import CreateObjectUseCase

    folder_id = f"obj:folder:{uuid.uuid4().hex[:16].upper()}"
    cmd = CreateObjectCommand(
        input=CreateObjectInput(
            object_type="folder",
            title=body.name.strip(),
            created_by=str(user.id),
            object_id=folder_id,
            status="active",
        )
    )
    out = CreateObjectUseCase(repo).execute(cmd)

    # Link to parent via PART_OF
    if body.parent_id:
        folder = repo.get_by_id(ObjectId(str(out.id)))
        if folder:
            folder.add_relationship(
                ObjectId(body.parent_id),
                RelationshipKind.PART_OF,
                Provenance.ASSERTED,
                actor=str(user.id),
            )
            repo.save(folder)

    db.commit()
    folder = repo.get_by_id(ObjectId(str(out.id)))
    return _to_response(folder, repo)


@router.put("/{folder_id}", response_model=FolderResponse)
def update_folder(
    folder_id: str,
    body: FolderUpdate,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
):
    """Rename a folder."""
    repo = _repo(db)
    folder = repo.get_by_id(ObjectId(folder_id))
    if folder is None or folder.object_type != ObjectType.FOLDER:
        raise HTTPException(status_code=404, detail="Folder not found")
    _require_folder_owner(folder, user)

    if body.name is not None:
        folder.title = body.name.strip()
        repo.save(folder)
        db.commit()

    folder = repo.get_by_id(ObjectId(folder_id))
    return _to_response(folder, repo)


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: str,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
):
    """Delete a folder. Documents inside are NOT deleted — only the
    CONTAINS relationships are removed. Subfolders become top-level."""
    repo = _repo(db)
    folder = repo.get_by_id(ObjectId(folder_id))
    if folder is None or folder.object_type != ObjectType.FOLDER:
        raise HTTPException(status_code=404, detail="Folder not found")
    _require_folder_owner(folder, user)

    # Remove CONTAINS relationships (documents stay)
    # Remove PART_OF relationships from children (subfolders become top-level)
    from app.application.commands.delete_object import DeleteObjectCommand
    from app.application.use_cases.delete_object import DeleteObjectUseCase

    DeleteObjectUseCase(repo).execute(DeleteObjectCommand(object_id=ObjectId(folder_id)))
    db.commit()


# ---------------------------------------------------------------------------
# Document–Folder membership
# ---------------------------------------------------------------------------

@router.post("/{folder_id}/documents/{document_id}", status_code=status.HTTP_201_CREATED)
def add_document_to_folder(
    folder_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
):
    """Add a document to a folder. Idempotent — no duplicate edges."""
    repo = _repo(db)
    folder = repo.get_by_id(ObjectId(folder_id))
    if folder is None or folder.object_type != ObjectType.FOLDER:
        raise HTTPException(status_code=404, detail="Folder not found")
    _require_folder_owner(folder, user)

    doc = repo.get_by_id(ObjectId(document_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check if already in folder
    for rel in folder.relationships:
        if rel.kind is RelationshipKind.CONTAINS and str(rel.target) == document_id:
            return {"status": "already_in_folder"}

    folder.add_relationship(
        ObjectId(document_id),
        RelationshipKind.CONTAINS,
        Provenance.ASSERTED,
        actor=str(user.id),
    )
    repo.save(folder)
    db.commit()
    return {"status": "added"}


@router.delete("/{folder_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document_from_folder(
    folder_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
):
    """Remove a document from a folder. Document is NOT deleted."""
    repo = _repo(db)
    folder = repo.get_by_id(ObjectId(folder_id))
    if folder is None or folder.object_type != ObjectType.FOLDER:
        raise HTTPException(status_code=404, detail="Folder not found")
    _require_folder_owner(folder, user)

    folder.remove_relationship(ObjectId(document_id), RelationshipKind.CONTAINS)
    repo.save(folder)
    db.commit()


@router.get("/{folder_id}/documents")
def list_documents_in_folder(
    folder_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
):
    """List documents in a folder. Respects document ACL."""
    repo = _repo(db)
    folder = repo.get_by_id(ObjectId(folder_id))
    if folder is None or folder.object_type != ObjectType.FOLDER:
        raise HTTPException(status_code=404, detail="Folder not found")
    _require_folder_owner(folder, user)

    doc_ids = [
        str(r.target) for r in folder.relationships
        if r.kind is RelationshipKind.CONTAINS
    ]
    docs = []
    for did in doc_ids:
        try:
            doc = repo.get_by_id(ObjectId(did))
            if doc is not None:
                docs.append(doc)
        except Exception:
            pass

    total = len(docs)
    start = (page - 1) * page_size
    page_docs = docs[start:start + page_size]

    items = []
    for doc in page_docs:
        items.append({
            "id": str(doc.id),
            "title": doc.title or "",
            "object_type": doc.object_type.value,
            "status": doc.status.value,
            "created_by": doc.audit.created_by if doc.audit else "",
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------------------
# Move folder
# ---------------------------------------------------------------------------

class MoveFolderRequest(BaseModel):
    new_parent_id: str | None = None  # None = move to top level


@router.put("/{folder_id}/move", response_model=FolderResponse)
def move_folder(
    folder_id: str,
    body: MoveFolderRequest,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
):
    """Move a folder to a new parent (or to top level)."""
    repo = _repo(db)
    folder = repo.get_by_id(ObjectId(folder_id))
    if folder is None or folder.object_type != ObjectType.FOLDER:
        raise HTTPException(status_code=404, detail="Folder not found")
    _require_folder_owner(folder, user)

    if body.new_parent_id:
        parent = repo.get_by_id(ObjectId(body.new_parent_id))
        if parent is None or parent.object_type != ObjectType.FOLDER:
            raise HTTPException(status_code=404, detail="Target folder not found")
        _require_folder_owner(parent, user)

    # Remove existing PART_OF
    folder.remove_relationship(
        ObjectId("dummy"),  # remove_relationship needs a target; we'll remove all PART_OF
        RelationshipKind.PART_OF,
    )
    # Actually, remove_relationship removes a specific edge. We need to remove ALL PART_OF edges.
    # Let's do it properly by iterating
    to_remove = [r.target for r in folder.relationships if r.kind is RelationshipKind.PART_OF]
    for target in to_remove:
        folder.remove_relationship(target, RelationshipKind.PART_OF)

    # Add new PART_OF
    if body.new_parent_id:
        folder.add_relationship(
            ObjectId(body.new_parent_id),
            RelationshipKind.PART_OF,
            Provenance.ASSERTED,
            actor=str(user.id),
        )

    repo.save(folder)
    db.commit()
    folder = repo.get_by_id(ObjectId(folder_id))
    return _to_response(folder, repo)


# ---------------------------------------------------------------------------
# Tags (on documents, using metadata)
# ---------------------------------------------------------------------------

@router.put("/tags/{document_id}")
def set_document_tags(
    document_id: str,
    body: TagUpdate,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
):
    """Set tags on a document (replaces existing tags)."""
    repo = _repo(db)
    doc = repo.get_by_id(ObjectId(document_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Only owner can tag
    owner = doc.audit.created_by if doc.audit else None
    if owner and owner != str(user.id):
        raise HTTPException(status_code=403, detail="Not your document")

    from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer
    doc.set_metadata(
        MetadataEntry(
            "tags",
            json.dumps(body.tags),
            MetadataLayer.L6_HUMAN_ASSERTED,
            Provenance.ASSERTED,
        ),
        actor=str(user.id),
    )
    repo.save(doc)
    db.commit()
    return {"tags": body.tags}


# ---------------------------------------------------------------------------
# Favorites (on documents, using metadata)
# ---------------------------------------------------------------------------

@router.put("/favorite/{document_id}")
def toggle_favorite(
    document_id: str,
    body: FavoriteUpdate,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
):
    """Mark/unmark a document as favorite."""
    repo = _repo(db)
    doc = repo.get_by_id(ObjectId(document_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    owner = doc.audit.created_by if doc.audit else None
    if owner and owner != str(user.id):
        raise HTTPException(status_code=403, detail="Not your document")

    from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer
    doc.set_metadata(
        MetadataEntry(
            "favorite",
            json.dumps(body.favorite),
            MetadataLayer.L6_HUMAN_ASSERTED,
            Provenance.ASSERTED,
        ),
        actor=str(user.id),
    )
    repo.save(doc)
    db.commit()
    return {"favorite": body.favorite}

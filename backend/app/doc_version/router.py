"""Document version management API endpoints.

Ported from v0.7.5 doc_version_server.py (port 8097).
"""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models.user import User
from . import service

router = APIRouter(prefix="/api/docs", tags=["doc_version"])


class IngestRequest(BaseModel):
    content: str
    title: str = "Untitled"
    source_file: str = ""
    project: str = "misc"
    doc_type: str = "other"
    tags: list[str] | None = None
    summary: str = ""


class RelationshipRequest(BaseModel):
    project: str
    from_doc_id: str
    to_doc_id: str
    rel_type: str
    description: str = ""


# ---- Ingest ----

@router.post("/ingest")
async def ingest_document(
    body: IngestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.ingest_document(
        db, user.id, body.content,
        title=body.title,
        source_file=body.source_file,
        project=body.project,
        doc_type=body.doc_type,
        tags=body.tags,
        summary=body.summary,
    )


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    project: str = "misc",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file and ingest as document."""
    raw = await file.read()
    text = raw.decode("utf-8", errors="replace")
    return await service.ingest_document(
        db, user.id, text,
        title=file.filename or "upload",
        source_file=file.filename or "",
        project=project,
    )


# ---- Read ----

@router.get("/list")
async def list_documents(
    project: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    docs = await service.list_documents(db, user.id, project)
    return {"documents": docs, "count": len(docs)}


@router.get("/recent")
async def get_recent(
    limit: int = 10,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    docs = await service.get_recent(db, user.id, limit)
    return {"documents": docs}


@router.get("/search")
async def search_documents(
    tag: str | None = None,
    type: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    docs = await service.search_documents(db, user.id, tag=tag, doc_type=type)
    return {"documents": docs, "count": len(docs)}


@router.get("/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_stats(db, user.id)


@router.get("/projects")
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    projects = await service.list_projects(db, user.id)
    return {"projects": projects}


@router.get("/{short_id}")
async def get_document(
    short_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await service.get_document(db, user.id, short_id)
    if not doc:
        return {"error": "Document not found"}
    return doc


@router.get("/{short_id}/latest")
async def get_latest(
    short_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.get_latest_content(db, user.id, short_id)
    if not result:
        return {"error": "Document not found"}
    return result


@router.get("/{short_id}/version/{version}")
async def get_version(
    short_id: str,
    version: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.get_version_content(db, user.id, short_id, version)
    if not result:
        return {"error": "Version not found"}
    return result


@router.get("/{short_id}/history")
async def get_history(
    short_id: str,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    history = await service.get_history(db, user.id, short_id, limit)
    return {"history": history}


@router.get("/{short_id}/diff")
async def get_diff(
    short_id: str,
    old: int = 1,
    new: int = 2,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.get_diff(db, user.id, short_id, old, new)
    if not result:
        return {"error": "Versions not found"}
    return result


@router.delete("/{short_id}")
async def delete_document(
    short_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await service.delete_document(db, user.id, short_id)
    if not ok:
        return {"error": "Document not found"}
    return {"status": "deleted", "doc_id": short_id}


# ---- Relationships ----

@router.post("/relationships")
async def add_relationship(
    body: RelationshipRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.add_relationship(
        db, user.id, body.project,
        body.from_doc_id, body.to_doc_id,
        body.rel_type, body.description,
    )
    if not result:
        return {"error": "Invalid relationship (check doc IDs and rel_type)"}
    return result


@router.get("/projects/{project}/relationships")
async def get_relationships(
    project: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rels = await service.get_relationships(db, user.id, project)
    return {"relationships": rels}


@router.get("/{short_id}/impact")
async def get_impact(
    short_id: str,
    project: str = "misc",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chain = await service.get_impact_chain(db, user.id, project, short_id)
    return {"doc_id": short_id, "impact_chain": chain}

"""RAG knowledge base API endpoints."""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models.user import User
from . import service

router = APIRouter(prefix="/api/rag", tags=["rag"])


class IngestTextRequest(BaseModel):
    content: str
    filename: str = "untitled.txt"
    metadata: dict | None = None


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/ingest")
async def ingest_text(
    body: IngestTextRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.ingest_text(
        db, user.id, body.content, body.filename, body.metadata
    )
    return result


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file and ingest its text content."""
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    result = await service.ingest_text(
        db, user.id, text, file.filename or "upload.txt"
    )
    return result


@router.post("/query")
async def query_knowledge(
    body: QueryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await service.query(db, user.id, body.query, body.top_k)
    return {"results": results, "count": len(results)}


@router.get("/documents")
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    docs = await service.list_documents(db, user.id)
    return {"documents": docs, "count": len(docs)}


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await service.delete_document(db, user.id, doc_id)
    if not ok:
        return {"error": "Document not found or not owned by you"}
    return {"status": "deleted", "document_id": str(doc_id)}


@router.get("/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_stats(db, user.id)

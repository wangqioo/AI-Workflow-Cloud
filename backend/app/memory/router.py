"""Memory API endpoints."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models.user import User
from . import service

router = APIRouter(prefix="/api/memory", tags=["memory"])


class SaveMemoryRequest(BaseModel):
    content: str
    category: str = "fact"
    importance: float = 0.5
    source_session: str | None = None


class SearchMemoryRequest(BaseModel):
    query: str
    top_k: int = 10
    category: str | None = None


class ConsolidateRequest(BaseModel):
    session_id: str
    messages: list[dict]


class CoreMemoryUpdate(BaseModel):
    block_type: str  # 'user' or 'agent'
    content: dict


@router.post("/save")
async def save_memory(
    body: SaveMemoryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.save_memory(
        db, user.id, body.content, body.category, body.importance, body.source_session
    )


@router.post("/search")
async def search_memory(
    body: SearchMemoryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await service.search_memory(db, user.id, body.query, body.top_k, body.category)
    return {"results": results}


@router.get("/context")
async def get_context(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    context = await service.get_context(db, user.id)
    return {"context": context, "length": len(context)}


@router.post("/consolidate")
async def consolidate(
    body: ConsolidateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.consolidate(db, user.id, body.session_id, body.messages)


@router.put("/core")
async def update_core_memory(
    body: CoreMemoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_core_memory(db, user.id, body.block_type, body.content)


@router.get("/core")
async def get_core_memory(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from ..models.memory import CoreMemory

    rows = (await db.execute(
        select(CoreMemory).where(CoreMemory.user_id == user.id)
    )).scalars().all()
    return {cm.block_type: {"content": cm.content, "version": cm.version} for cm in rows}

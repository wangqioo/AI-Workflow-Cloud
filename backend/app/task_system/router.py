"""Task management API endpoints.

Ported from v0.7.5 task_agent_server.py (port 8130).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models.user import User
from . import service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ---- Request schemas ----

class CreateTaskRequest(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    category: str = ""
    tags: list[str] | None = None
    requirements: list[str] | None = None
    context: str = ""
    expected_deliverables: list[str] | None = None
    deadline: datetime | None = None
    receiver_name: str = ""


class UpdateTaskRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    requirements: list[str] | None = None
    expected_deliverables: list[str] | None = None
    deadline: datetime | None = None
    receiver_name: str | None = None


class TransitionRequest(BaseModel):
    target_status: str
    message: str = ""


class MessageRequest(BaseModel):
    content: str
    msg_type: str = "text_message"


class ProgressRequest(BaseModel):
    percentage: int
    description: str = ""
    milestone: str = ""


class ResultRequest(BaseModel):
    summary: str
    details: str = ""
    deliverables: list[str] | None = None


class SearchRequest(BaseModel):
    query: str
    limit: int = 20


class TemplateCreateRequest(BaseModel):
    name: str
    description: str = ""
    task_body: dict


# ---- CRUD ----

@router.post("")
async def create_task(
    body: CreateTaskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_task(
        db, user.id, body.title,
        description=body.description,
        priority=body.priority,
        category=body.category,
        tags=body.tags,
        requirements=body.requirements,
        context=body.context,
        expected_deliverables=body.expected_deliverables,
        deadline=body.deadline,
        receiver_name=body.receiver_name,
        sender_name=user.display_name or user.username,
    )


@router.get("")
async def list_tasks(
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    archived: bool = False,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks = await service.list_tasks(
        db, user.id, status=status, priority=priority,
        category=category, include_archived=archived,
        limit=limit, offset=offset,
    )
    return {"tasks": tasks, "count": len(tasks)}


@router.get("/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_stats(db, user.id)


@router.post("/search")
async def search_tasks(
    body: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks = await service.search_tasks(db, user.id, body.query, body.limit)
    return {"tasks": tasks, "count": len(tasks)}


# ---- Templates (must be before /{short_id} to avoid route conflict) ----

@router.post("/templates")
async def create_template(
    body: TemplateCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_template(db, user.id, body.name, body.task_body, body.description)


@router.get("/templates")
async def list_templates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    templates = await service.list_templates(db, user.id)
    return {"templates": templates}


@router.post("/templates/{template_id}/apply")
async def apply_template(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.apply_template(db, user.id, template_id)
    if not result:
        return {"error": "Template not found"}
    return result


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await service.delete_template(db, user.id, template_id)
    if not ok:
        return {"error": "Template not found"}
    return {"status": "deleted"}


@router.get("/{short_id}")
async def get_task(
    short_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await service.get_task(db, user.id, short_id)
    if not task:
        return {"error": "Task not found"}
    return task


@router.put("/{short_id}")
async def update_task(
    short_id: str,
    body: UpdateTaskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updates = body.model_dump(exclude_none=True)
    result = await service.update_task(db, user.id, short_id, updates)
    if not result:
        return {"error": "Task not found"}
    return result


@router.delete("/{short_id}")
async def delete_task(
    short_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await service.delete_task(db, user.id, short_id)
    if not ok:
        return {"error": "Task not found"}
    return {"status": "deleted"}


# ---- Workflow ----

@router.post("/{short_id}/transition")
async def transition_task(
    short_id: str,
    body: TransitionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.transition(db, user.id, short_id, body.target_status, body.message)
    if not result:
        return {"error": "Task not found"}
    return result


@router.post("/{short_id}/messages")
async def add_message(
    short_id: str,
    body: MessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.add_message(
        db, user.id, short_id, body.content, body.msg_type,
        from_user=user.display_name or user.username,
    )
    if not result:
        return {"error": "Task not found"}
    return result


@router.get("/{short_id}/messages")
async def get_messages(
    short_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msgs = await service.get_messages(db, user.id, short_id)
    return {"messages": msgs}


@router.post("/{short_id}/progress")
async def update_progress(
    short_id: str,
    body: ProgressRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.update_progress(db, user.id, short_id, body.percentage, body.description, body.milestone)
    if not result:
        return {"error": "Task not found"}
    return result


@router.post("/{short_id}/result")
async def submit_result(
    short_id: str,
    body: ResultRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.submit_result(db, user.id, short_id, body.summary, body.details, body.deliverables)
    if not result:
        return {"error": "Task not found"}
    return result


@router.post("/{short_id}/archive")
async def archive_task(
    short_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await service.archive_task(db, user.id, short_id)
    if not ok:
        return {"error": "Task not found or not in closed/rejected status"}
    return {"status": "archived"}

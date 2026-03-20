"""Task management service.

Ported from v0.7.5 task_agent (task_storage + task_models + task_templates + task_analytics).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.task import (
    VALID_TRANSITIONS, Task, TaskMessage, TaskTemplate,
)


def _task_short_id() -> str:
    now = datetime.now(timezone.utc)
    return f"task_{now.strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"


# ---- Create ----

async def create_task(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    *,
    description: str = "",
    priority: str = "medium",
    category: str = "",
    tags: list[str] | None = None,
    requirements: list[str] | None = None,
    context: str = "",
    expected_deliverables: list[str] | None = None,
    deadline: datetime | None = None,
    receiver_name: str = "",
    sender_name: str = "",
) -> dict:
    task = Task(
        user_id=user_id,
        short_id=_task_short_id(),
        title=title,
        description=description,
        status="draft",
        priority=priority,
        category=category,
        tags=tags or [],
        requirements=requirements or [],
        context=context,
        expected_deliverables=expected_deliverables or [],
        deadline=deadline,
        sender_name=sender_name,
        receiver_name=receiver_name,
    )
    db.add(task)
    await db.flush()

    msg = TaskMessage(
        task_id=task.id,
        from_user=sender_name or "system",
        msg_type="task_created",
        content=f"Task created: {title}",
    )
    db.add(msg)
    return _task_to_dict(task)


# ---- Read ----

async def get_task(db: AsyncSession, user_id: uuid.UUID, short_id: str) -> dict | None:
    task = await _find_task(db, user_id, short_id)
    return _task_to_dict(task) if task else None


async def list_tasks(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    stmt = select(Task).where(Task.user_id == user_id)
    if not include_archived:
        stmt = stmt.where(Task.is_archived.is_(False))
    if status:
        stmt = stmt.where(Task.status == status)
    if priority:
        stmt = stmt.where(Task.priority == priority)
    if category:
        stmt = stmt.where(Task.category == category)
    stmt = stmt.order_by(Task.updated_at.desc()).offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_task_to_dict(t) for t in rows]


async def search_tasks(
    db: AsyncSession, user_id: uuid.UUID, query: str, limit: int = 20
) -> list[dict]:
    """Simple text search on title and description."""
    pattern = f"%{query}%"
    stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.is_archived.is_(False),
            (Task.title.ilike(pattern) | Task.description.ilike(pattern)),
        )
        .order_by(Task.updated_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_task_to_dict(t) for t in rows]


# ---- Update ----

async def update_task(
    db: AsyncSession, user_id: uuid.UUID, short_id: str, updates: dict
) -> dict | None:
    task = await _find_task(db, user_id, short_id)
    if not task:
        return None
    # Only allow edit in draft status
    if task.status != "draft":
        return {"error": "Can only edit tasks in draft status"}

    allowed = {"title", "description", "priority", "category", "tags", "requirements", "context", "expected_deliverables", "deadline", "receiver_name"}
    for key, val in updates.items():
        if key in allowed:
            setattr(task, key, val)
    return _task_to_dict(task)


async def delete_task(db: AsyncSession, user_id: uuid.UUID, short_id: str) -> bool:
    task = await _find_task(db, user_id, short_id)
    if not task:
        return False
    await db.delete(task)
    return True


# ---- Status transitions ----

async def transition(
    db: AsyncSession,
    user_id: uuid.UUID,
    short_id: str,
    target_status: str,
    message: str = "",
) -> dict | None:
    task = await _find_task(db, user_id, short_id)
    if not task:
        return None

    valid = VALID_TRANSITIONS.get(task.status, [])
    if target_status not in valid:
        return {"error": f"Cannot transition from '{task.status}' to '{target_status}'", "valid_targets": valid}

    old_status = task.status
    task.status = target_status

    msg = TaskMessage(
        task_id=task.id,
        from_user="system",
        msg_type=f"status_{target_status}",
        content=message or f"Status changed: {old_status} -> {target_status}",
    )
    db.add(msg)
    return _task_to_dict(task)


# ---- Messages ----

async def add_message(
    db: AsyncSession,
    user_id: uuid.UUID,
    short_id: str,
    content: str,
    msg_type: str = "text_message",
    from_user: str = "",
) -> dict | None:
    task = await _find_task(db, user_id, short_id)
    if not task:
        return None
    msg = TaskMessage(
        task_id=task.id,
        from_user=from_user or "user",
        msg_type=msg_type,
        content=content,
    )
    db.add(msg)
    await db.flush()
    return {"message_id": str(msg.id), "type": msg.msg_type, "content": msg.content}


async def get_messages(
    db: AsyncSession, user_id: uuid.UUID, short_id: str
) -> list[dict]:
    task = await _find_task(db, user_id, short_id)
    if not task:
        return []
    rows = (await db.execute(
        select(TaskMessage).where(TaskMessage.task_id == task.id).order_by(TaskMessage.created_at)
    )).scalars().all()
    return [
        {"message_id": str(m.id), "from": m.from_user, "type": m.msg_type, "content": m.content, "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in rows
    ]


# ---- Progress ----

async def update_progress(
    db: AsyncSession, user_id: uuid.UUID, short_id: str,
    percentage: int, description: str = "", milestone: str = ""
) -> dict | None:
    task = await _find_task(db, user_id, short_id)
    if not task:
        return None
    task.progress_pct = max(0, min(100, percentage))
    task.progress_desc = description
    if milestone:
        task.progress_milestone = milestone

    msg = TaskMessage(
        task_id=task.id,
        from_user="system",
        msg_type="progress_update",
        content=f"Progress: {percentage}% - {description}",
        metadata={"percentage": percentage, "milestone": milestone},
    )
    db.add(msg)
    return _task_to_dict(task)


# ---- Result ----

async def submit_result(
    db: AsyncSession, user_id: uuid.UUID, short_id: str,
    summary: str, details: str = "", deliverables: list[str] | None = None
) -> dict | None:
    task = await _find_task(db, user_id, short_id)
    if not task:
        return None
    task.result = {
        "summary": summary,
        "details": details,
        "deliverables": deliverables or [],
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    msg = TaskMessage(
        task_id=task.id,
        from_user="system",
        msg_type="result_submitted",
        content=f"Result submitted: {summary}",
    )
    db.add(msg)
    return _task_to_dict(task)


# ---- Archive ----

async def archive_task(db: AsyncSession, user_id: uuid.UUID, short_id: str) -> bool:
    task = await _find_task(db, user_id, short_id)
    if not task or task.status not in ("closed", "rejected"):
        return False
    task.is_archived = True
    return True


# ---- Templates ----

async def create_template(
    db: AsyncSession, user_id: uuid.UUID,
    name: str, task_body: dict, description: str = ""
) -> dict:
    tpl = TaskTemplate(
        user_id=user_id, name=name, description=description, task_body=task_body
    )
    db.add(tpl)
    await db.flush()
    return _tpl_to_dict(tpl)


async def list_templates(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = (await db.execute(
        select(TaskTemplate).where(TaskTemplate.user_id == user_id).order_by(TaskTemplate.use_count.desc())
    )).scalars().all()
    return [_tpl_to_dict(t) for t in rows]


async def apply_template(
    db: AsyncSession, user_id: uuid.UUID, template_id: uuid.UUID
) -> dict | None:
    tpl = (await db.execute(
        select(TaskTemplate).where(TaskTemplate.id == template_id, TaskTemplate.user_id == user_id)
    )).scalar_one_or_none()
    if not tpl:
        return None
    tpl.use_count += 1
    body = tpl.task_body
    return await create_task(
        db, user_id,
        title=body.get("title", tpl.name),
        description=body.get("description", ""),
        priority=body.get("priority", "medium"),
        category=body.get("category", ""),
        tags=body.get("tags"),
        requirements=body.get("requirements"),
        expected_deliverables=body.get("expected_deliverables"),
    )


async def delete_template(db: AsyncSession, user_id: uuid.UUID, template_id: uuid.UUID) -> bool:
    tpl = (await db.execute(
        select(TaskTemplate).where(TaskTemplate.id == template_id, TaskTemplate.user_id == user_id)
    )).scalar_one_or_none()
    if not tpl:
        return False
    await db.delete(tpl)
    return True


# ---- Analytics ----

async def get_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
    total = (await db.execute(
        select(func.count()).select_from(Task).where(Task.user_id == user_id, Task.is_archived.is_(False))
    )).scalar() or 0

    # By status
    status_rows = (await db.execute(
        select(Task.status, func.count())
        .where(Task.user_id == user_id, Task.is_archived.is_(False))
        .group_by(Task.status)
    )).all()
    by_status = {row[0]: row[1] for row in status_rows}

    # By priority
    prio_rows = (await db.execute(
        select(Task.priority, func.count())
        .where(Task.user_id == user_id, Task.is_archived.is_(False))
        .group_by(Task.priority)
    )).all()
    by_priority = {row[0]: row[1] for row in prio_rows}

    completed = by_status.get("completed", 0) + by_status.get("delivered", 0) + by_status.get("closed", 0)
    completion_rate = round(completed / total * 100, 1) if total > 0 else 0

    return {
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "completed": completed,
        "completion_rate": completion_rate,
    }


# ---- Helpers ----

async def _find_task(db: AsyncSession, user_id: uuid.UUID, short_id: str) -> Task | None:
    return (await db.execute(
        select(Task).where(Task.user_id == user_id, Task.short_id == short_id)
    )).scalar_one_or_none()


def _task_to_dict(task: Task) -> dict:
    return {
        "task_id": task.short_id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "category": task.category,
        "tags": task.tags,
        "requirements": task.requirements,
        "context": task.context,
        "expected_deliverables": task.expected_deliverables,
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "sender_name": task.sender_name,
        "receiver_name": task.receiver_name,
        "progress": {
            "percentage": task.progress_pct,
            "description": task.progress_desc,
            "milestone": task.progress_milestone,
        },
        "result": task.result,
        "ai_summary": task.ai_summary,
        "is_archived": task.is_archived,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def _tpl_to_dict(tpl: TaskTemplate) -> dict:
    return {
        "template_id": str(tpl.id),
        "name": tpl.name,
        "description": tpl.description,
        "task_body": tpl.task_body,
        "use_count": tpl.use_count,
        "created_at": tpl.created_at.isoformat() if tpl.created_at else None,
    }

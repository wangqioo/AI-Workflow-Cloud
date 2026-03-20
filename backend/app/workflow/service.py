"""Workflow CRUD and execution service.

Ported from v0.7.5 file-based WorkflowStorage + WorkflowInterface
to PostgreSQL-backed async service.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.workflow import Workflow, WorkflowExecution
from .engine import execute_workflow


# ---- CRUD ----

async def create_workflow(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    definition: dict,
    *,
    slug: str | None = None,
    description: str = "",
    category: str = "general",
    source: str = "user",
    workflow_type: str = "pipeline",
    manifest: dict | None = None,
    ui_definition: dict | None = None,
    input_schema: dict | None = None,
    output_schema: dict | None = None,
    tags: list[str] | None = None,
    engines_required: list[str] | None = None,
) -> dict:
    if not slug:
        slug = name.lower().replace(" ", "_")[:128]

    wf = Workflow(
        user_id=user_id,
        slug=slug,
        name=name,
        description=description,
        category=category,
        source=source,
        workflow_type=workflow_type,
        definition=definition,
        manifest=manifest or {},
        ui_definition=ui_definition or {},
        input_schema=input_schema or {},
        output_schema=output_schema or {},
        tags=tags or [],
        engines_required=engines_required or [],
    )
    db.add(wf)
    await db.flush()
    return _wf_to_dict(wf)


async def update_workflow(
    db: AsyncSession,
    user_id: uuid.UUID,
    workflow_id: uuid.UUID,
    updates: dict,
) -> dict | None:
    wf = (await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id, Workflow.is_active.is_(True))
    )).scalar_one_or_none()
    if not wf:
        return None

    allowed = {"name", "description", "category", "definition", "ui_definition", "input_schema", "output_schema", "tags", "engines_required", "slug"}
    for key, val in updates.items():
        if key in allowed:
            setattr(wf, key, val)
    return _wf_to_dict(wf)


async def get_workflow(
    db: AsyncSession, user_id: uuid.UUID, workflow_id: uuid.UUID
) -> dict | None:
    wf = (await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id, Workflow.is_active.is_(True))
    )).scalar_one_or_none()
    return _wf_to_dict(wf) if wf else None


async def list_workflows(
    db: AsyncSession, user_id: uuid.UUID, category: str | None = None
) -> list[dict]:
    stmt = select(Workflow).where(Workflow.user_id == user_id, Workflow.is_active.is_(True))
    if category:
        stmt = stmt.where(Workflow.category == category)
    stmt = stmt.order_by(Workflow.updated_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_wf_to_dict(wf) for wf in rows]


async def delete_workflow(
    db: AsyncSession, user_id: uuid.UUID, workflow_id: uuid.UUID
) -> bool:
    """Soft-delete a workflow."""
    wf = (await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id, Workflow.is_active.is_(True))
    )).scalar_one_or_none()
    if not wf:
        return False
    wf.is_active = False
    return True


# ---- Validation ----

async def validate_workflow(definition: dict) -> dict:
    """Validate a workflow definition. Returns {valid, errors}."""
    errors = []

    if "name" not in definition and "workflow" not in definition:
        errors.append("Missing 'name' or 'workflow' field")

    wf = definition.get("workflow", definition)
    has_nodes = "nodes" in wf and "connections" in wf
    has_steps = "steps" in wf

    if not has_nodes and not has_steps:
        errors.append("Workflow must contain 'nodes'+'connections' (n8n) or 'steps' (legacy)")

    if has_nodes:
        nodes = wf.get("nodes", [])
        if not nodes:
            errors.append("Workflow has no nodes")
        for i, node in enumerate(nodes):
            if "name" not in node:
                errors.append(f"Node {i} missing 'name'")
            if "type" not in node:
                errors.append(f"Node {i} missing 'type'")

    if has_steps:
        steps = wf.get("steps", [])
        if not steps:
            errors.append("Workflow has no steps")
        seen_ids = set()
        for i, step in enumerate(steps):
            sid = step.get("id", "")
            if not sid:
                errors.append(f"Step {i} missing 'id'")
            elif sid in seen_ids:
                errors.append(f"Duplicate step id: {sid}")
            seen_ids.add(sid)

    return {"valid": len(errors) == 0, "errors": errors}


# ---- Execution ----

async def execute(
    db: AsyncSession,
    user_id: uuid.UUID,
    workflow_id: uuid.UUID,
    input_data: dict | None = None,
    trigger_data: dict | None = None,
) -> dict:
    """Execute a workflow and record the result."""
    wf = (await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id, Workflow.is_active.is_(True))
    )).scalar_one_or_none()
    if not wf:
        return {"error": "Workflow not found"}

    # Create execution record
    exe = WorkflowExecution(
        workflow_id=wf.id,
        user_id=user_id,
        status="running",
        input_data=input_data or {},
        trigger_data=trigger_data or {},
    )
    db.add(exe)
    await db.flush()

    # Run engine
    try:
        result = await execute_workflow(
            wf.definition, input_data=input_data, trigger_data=trigger_data
        )
        exe.status = result.get("status", "error")
        exe.steps_completed = result.get("steps_completed", 0)
        exe.steps_failed = result.get("steps_failed", 0)
        exe.execution_time_ms = result.get("execution_time_ms", 0)
        exe.results = result.get("results", {})
        exe.error = result.get("error")
    except Exception as e:
        exe.status = "error"
        exe.error = str(e)

    exe.completed_at = datetime.now(timezone.utc)
    return _exe_to_dict(exe)


# ---- Webhook ----

async def register_webhook(
    db: AsyncSession, user_id: uuid.UUID, workflow_id: uuid.UUID
) -> dict | None:
    wf = (await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id, Workflow.is_active.is_(True))
    )).scalar_one_or_none()
    if not wf:
        return None
    if not wf.webhook_token:
        wf.webhook_token = uuid.uuid4().hex
    return {"workflow_id": str(wf.id), "token": wf.webhook_token}


async def unregister_webhook(
    db: AsyncSession, user_id: uuid.UUID, workflow_id: uuid.UUID
) -> bool:
    wf = (await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )).scalar_one_or_none()
    if not wf:
        return False
    wf.webhook_token = None
    return True


async def execute_webhook(
    db: AsyncSession, token: str, trigger_data: dict | None = None
) -> dict:
    """Execute a workflow via webhook token."""
    wf = (await db.execute(
        select(Workflow).where(Workflow.webhook_token == token, Workflow.is_active.is_(True))
    )).scalar_one_or_none()
    if not wf:
        return {"error": "Invalid webhook token"}
    return await execute(db, wf.user_id, wf.id, trigger_data=trigger_data)


# ---- History ----

async def get_history(
    db: AsyncSession, user_id: uuid.UUID, workflow_id: uuid.UUID | None = None, limit: int = 20
) -> list[dict]:
    stmt = select(WorkflowExecution).where(WorkflowExecution.user_id == user_id)
    if workflow_id:
        stmt = stmt.where(WorkflowExecution.workflow_id == workflow_id)
    stmt = stmt.order_by(WorkflowExecution.started_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_exe_to_dict(e) for e in rows]


async def get_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
    total = (await db.execute(
        select(func.count()).select_from(WorkflowExecution).where(WorkflowExecution.user_id == user_id)
    )).scalar() or 0
    success = (await db.execute(
        select(func.count()).select_from(WorkflowExecution).where(
            WorkflowExecution.user_id == user_id, WorkflowExecution.status == "success"
        )
    )).scalar() or 0
    wf_count = (await db.execute(
        select(func.count()).select_from(Workflow).where(Workflow.user_id == user_id, Workflow.is_active.is_(True))
    )).scalar() or 0

    return {
        "total_workflows": wf_count,
        "total_executions": total,
        "successful_executions": success,
        "failed_executions": total - success,
    }


# ---- Serializers ----

def _wf_to_dict(wf: Workflow) -> dict:
    return {
        "id": str(wf.id),
        "slug": wf.slug,
        "name": wf.name,
        "description": wf.description,
        "version": wf.version,
        "category": wf.category,
        "source": wf.source,
        "workflow_type": wf.workflow_type,
        "definition": wf.definition,
        "manifest": wf.manifest,
        "ui_definition": wf.ui_definition,
        "input_schema": wf.input_schema,
        "output_schema": wf.output_schema,
        "tags": wf.tags,
        "engines_required": wf.engines_required,
        "has_webhook": wf.webhook_token is not None,
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
    }


def _exe_to_dict(exe: WorkflowExecution) -> dict:
    return {
        "id": str(exe.id),
        "workflow_id": str(exe.workflow_id),
        "status": exe.status,
        "steps_completed": exe.steps_completed,
        "steps_failed": exe.steps_failed,
        "execution_time_ms": exe.execution_time_ms,
        "input_data": exe.input_data,
        "trigger_data": exe.trigger_data,
        "results": exe.results,
        "error": exe.error,
        "started_at": exe.started_at.isoformat() if exe.started_at else None,
        "completed_at": exe.completed_at.isoformat() if exe.completed_at else None,
    }

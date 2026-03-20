"""Workflow API endpoints.

Ported from v0.7.5 adapter_server.py (port 8105) workflow routes.
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models.user import User
from . import service

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


# ---- Request schemas ----

class CreateWorkflowRequest(BaseModel):
    name: str
    definition: dict
    slug: str | None = None
    description: str = ""
    category: str = "general"
    workflow_type: str = "pipeline"
    ui_definition: dict | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    tags: list[str] | None = None
    engines_required: list[str] | None = None


class UpdateWorkflowRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    definition: dict | None = None
    ui_definition: dict | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    tags: list[str] | None = None
    slug: str | None = None


class ExecuteRequest(BaseModel):
    input_data: dict | None = None
    trigger_data: dict | None = None


class ValidateRequest(BaseModel):
    definition: dict


class WebhookTriggerRequest(BaseModel):
    data: dict | None = None


# ---- CRUD ----

@router.post("/create")
async def create_workflow(
    body: CreateWorkflowRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_workflow(
        db, user.id, body.name, body.definition,
        slug=body.slug,
        description=body.description,
        category=body.category,
        workflow_type=body.workflow_type,
        ui_definition=body.ui_definition,
        input_schema=body.input_schema,
        output_schema=body.output_schema,
        tags=body.tags,
        engines_required=body.engines_required,
    )


@router.get("/list")
async def list_workflows(
    category: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workflows = await service.list_workflows(db, user.id, category)
    return {"workflows": workflows, "count": len(workflows)}


@router.get("/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_stats(db, user.id)


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wf = await service.get_workflow(db, user.id, workflow_id)
    if not wf:
        return {"error": "Workflow not found"}
    return wf


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: uuid.UUID,
    body: UpdateWorkflowRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updates = body.model_dump(exclude_none=True)
    result = await service.update_workflow(db, user.id, workflow_id, updates)
    if not result:
        return {"error": "Workflow not found"}
    return result


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await service.delete_workflow(db, user.id, workflow_id)
    if not ok:
        return {"error": "Workflow not found"}
    return {"status": "deleted", "workflow_id": str(workflow_id)}


# ---- Validation ----

@router.post("/validate")
async def validate_workflow(body: ValidateRequest):
    return await service.validate_workflow(body.definition)


# ---- Execution ----

@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: uuid.UUID,
    body: ExecuteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.execute(db, user.id, workflow_id, body.input_data, body.trigger_data)


@router.get("/{workflow_id}/history")
async def get_workflow_history(
    workflow_id: uuid.UUID,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    history = await service.get_history(db, user.id, workflow_id, limit)
    return {"history": history, "count": len(history)}


@router.get("/history/all")
async def get_all_history(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    history = await service.get_history(db, user.id, limit=limit)
    return {"history": history, "count": len(history)}


# ---- Webhooks ----

@router.post("/{workflow_id}/webhook/register")
async def register_webhook(
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await service.register_webhook(db, user.id, workflow_id)
    if not result:
        return {"error": "Workflow not found"}
    return result


@router.delete("/{workflow_id}/webhook")
async def unregister_webhook(
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await service.unregister_webhook(db, user.id, workflow_id)
    if not ok:
        return {"error": "Workflow not found"}
    return {"status": "unregistered"}


# Webhook trigger (no auth — token-based)
@router.post("/webhook/{token}")
async def trigger_webhook(
    token: str,
    body: WebhookTriggerRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    trigger_data = body.data if body else None
    return await service.execute_webhook(db, token, trigger_data)

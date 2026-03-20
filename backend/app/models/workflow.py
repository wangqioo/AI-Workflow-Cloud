"""Workflow database models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy import JSON as JSONB  # portable across PostgreSQL/SQLite
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    slug: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    category: Mapped[str] = mapped_column(String(64), default="general")
    source: Mapped[str] = mapped_column(String(32), default="user")  # user/builtin/n8n_import
    workflow_type: Mapped[str] = mapped_column(String(32), default="pipeline")  # pipeline/scripted

    # Full workflow definition (n8n nodes+connections or steps format) stored as JSONB
    definition: Mapped[dict] = mapped_column(JSONB, default=dict)
    # OCW manifest metadata
    manifest: Mapped[dict] = mapped_column(JSONB, default=dict)
    # UI layout definition
    ui_definition: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Input/output schema
    input_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSONB, default=dict)

    tags: Mapped[list] = mapped_column(JSONB, default=list)
    engines_required: Mapped[list] = mapped_column(JSONB, default=list)

    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Webhook token (nullable, set when registered)
    webhook_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    executions: Mapped[list["WorkflowExecution"]] = relationship(back_populates="workflow", cascade="all, delete-orphan")


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)

    status: Mapped[str] = mapped_column(String(32), default="running")  # running/success/error/timeout
    steps_completed: Mapped[int] = mapped_column(Integer, default=0)
    steps_failed: Mapped[int] = mapped_column(Integer, default=0)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0)

    input_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    trigger_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    results: Mapped[dict] = mapped_column(JSONB, default=dict)  # step-by-step results
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow: Mapped["Workflow"] = relationship(back_populates="executions")

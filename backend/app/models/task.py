"""Task management models.

Ported from v0.7.5 task_agent (JSON files) to PostgreSQL.
Simplified: user-based auth replaces device identity, no crypto signing.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

# Status transition rules
VALID_TRANSITIONS = {
    "draft": ["sent"],
    "sent": ["received"],
    "received": ["accepted", "rejected"],
    "accepted": ["in_progress"],
    "in_progress": ["clarification_needed", "completed"],
    "clarification_needed": ["in_progress"],
    "completed": ["delivered", "in_progress"],
    "delivered": ["closed"],
}

PRIORITY_LEVELS = ["low", "medium", "high", "urgent"]


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    short_id: Mapped[str] = mapped_column(String(24), unique=True, index=True)

    # Core fields
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    priority: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    category: Mapped[str] = mapped_column(String(128), default="")
    tags: Mapped[list] = mapped_column(JSONB, default=list)

    # Task details
    requirements: Mapped[list] = mapped_column(JSONB, default=list)
    context: Mapped[str] = mapped_column(Text, default="")
    expected_deliverables: Mapped[list] = mapped_column(JSONB, default=list)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Sender/receiver (user-based in cloud mode)
    sender_name: Mapped[str] = mapped_column(String(128), default="")
    receiver_name: Mapped[str] = mapped_column(String(128), default="")
    receiver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Progress
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    progress_desc: Mapped[str] = mapped_column(Text, default="")
    progress_milestone: Mapped[str] = mapped_column(String(256), default="")

    # Result
    result: Mapped[dict] = mapped_column(JSONB, default=dict)

    # AI analysis
    ai_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    ai_result_check: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Grouping
    batch_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    template_id: Mapped[str] = mapped_column(String(64), default="")

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages: Mapped[list["TaskMessage"]] = relationship(back_populates="task", cascade="all, delete-orphan", order_by="TaskMessage.created_at")


class TaskMessage(Base):
    """Message timeline entry for a task."""

    __tablename__ = "task_messages"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    from_user: Mapped[str] = mapped_column(String(128))
    msg_type: Mapped[str] = mapped_column(String(32))  # task_created, progress_update, text_message, etc.
    content: Mapped[str] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["Task"] = relationship(back_populates="messages")


class TaskTemplate(Base):
    """Reusable task template."""

    __tablename__ = "task_templates"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    task_body: Mapped[dict] = mapped_column(JSONB, default=dict)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

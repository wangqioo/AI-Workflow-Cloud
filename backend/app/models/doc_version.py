"""Document version management models.

Ported from v0.7.5 Git+JSON file storage to PostgreSQL.
Full version content stored in DB (no Git dependency in cloud mode).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy import JSON as JSONB  # portable across PostgreSQL/SQLite
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class VersionedDocument(Base):
    """Main document record (replaces .doc_index.json entries)."""

    __tablename__ = "versioned_documents"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    short_id: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    source_file: Mapped[str] = mapped_column(String(512), default="")
    source_hash: Mapped[str] = mapped_column(String(72), default="", index=True)
    project: Mapped[str] = mapped_column(String(255), default="misc", index=True)
    version_count: Mapped[int] = mapped_column(Integer, default=1)

    # AI analysis
    doc_type: Mapped[str] = mapped_column(String(50), default="other", index=True)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    key_entities: Mapped[list] = mapped_column(JSONB, default=list)
    key_dates: Mapped[list] = mapped_column(JSONB, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    diff_summaries: Mapped[list] = mapped_column(JSONB, default=list)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentVersion(Base):
    """Individual version snapshot (replaces Git commits)."""

    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    doc_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("versioned_documents.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    diff_text: Mapped[str] = mapped_column(Text, default="")
    diff_summary: Mapped[str] = mapped_column(Text, default="")
    lines_added: Mapped[int] = mapped_column(Integer, default=0)
    lines_removed: Mapped[int] = mapped_column(Integer, default=0)
    commit_message: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["VersionedDocument"] = relationship(back_populates="versions")


class DocProject(Base):
    """Project grouping for documents."""

    __tablename__ = "doc_projects"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    doc_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DocRelationship(Base):
    """Document relationship edges (drives, constrains, references, etc.)."""

    __tablename__ = "doc_relationships"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    project: Mapped[str] = mapped_column(String(255), index=True)
    from_doc_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("versioned_documents.id", ondelete="CASCADE"))
    to_doc_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("versioned_documents.id", ondelete="CASCADE"))
    rel_type: Mapped[str] = mapped_column(String(50))  # drives/constrains/references/supersedes/supplements
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

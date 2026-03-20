"""Document version management service.

Ported from v0.7.5 doc_version_server + doc_index + doc_git + doc_project.
All storage now in PostgreSQL (no Git/JSON files).
"""

from __future__ import annotations

import difflib
import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.doc_version import (
    DocProject, DocRelationship, DocumentVersion, VersionedDocument,
)

RELATION_TYPES = {
    "drives": "A drives B (e.g. requirements drive design)",
    "constrains": "A constrains B (e.g. contract constrains requirements)",
    "references": "A references B (e.g. meeting notes reference requirements)",
    "supersedes": "A supersedes B (e.g. new spec replaces old)",
    "supplements": "A supplements B (e.g. attachment supplements main doc)",
}


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _content_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()[:16]


def _compute_diff(old: str, new: str) -> tuple[str, int, int]:
    """Compute unified diff, return (diff_text, lines_added, lines_removed)."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    return "".join(diff), added, removed


# ---- Ingest ----

async def ingest_document(
    db: AsyncSession,
    user_id: uuid.UUID,
    content: str,
    *,
    title: str = "Untitled",
    source_file: str = "",
    project: str = "misc",
    doc_type: str = "other",
    tags: list[str] | None = None,
    summary: str = "",
) -> dict:
    """Ingest a document. If source_hash matches, skip. If source_file matches, update."""
    content_hash = _content_hash(content)

    # Level 1: exact hash match → skip
    existing = (await db.execute(
        select(VersionedDocument).where(
            VersionedDocument.user_id == user_id,
            VersionedDocument.source_hash == content_hash,
            VersionedDocument.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if existing:
        return {"action": "skipped", "reason": "identical_content", "doc_id": existing.short_id, "document": _doc_to_dict(existing)}

    # Level 1: filename match → update
    if source_file:
        existing = (await db.execute(
            select(VersionedDocument).where(
                VersionedDocument.user_id == user_id,
                VersionedDocument.source_file == source_file,
                VersionedDocument.is_active.is_(True),
            )
        )).scalar_one_or_none()
        if existing:
            return await _update_document(db, existing, content, content_hash)

    # New document
    doc = VersionedDocument(
        user_id=user_id,
        short_id=_short_id(),
        title=title,
        source_file=source_file,
        source_hash=content_hash,
        project=project,
        version_count=1,
        doc_type=doc_type,
        tags=tags or [],
        summary=summary,
    )
    db.add(doc)
    await db.flush()

    ver = DocumentVersion(
        doc_id=doc.id,
        version_number=1,
        content=content,
        commit_message=f"Initial version of {title}",
    )
    db.add(ver)

    # Ensure project exists
    await _ensure_project(db, user_id, project)

    return {"action": "created", "doc_id": doc.short_id, "document": _doc_to_dict(doc)}


async def _update_document(
    db: AsyncSession, doc: VersionedDocument, content: str, content_hash: str
) -> dict:
    """Create new version for existing document."""
    # Get previous version content
    prev = (await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.doc_id == doc.id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )).scalar_one_or_none()

    diff_text, added, removed = "", 0, 0
    if prev:
        diff_text, added, removed = _compute_diff(prev.content, content)

    new_ver = doc.version_count + 1
    ver = DocumentVersion(
        doc_id=doc.id,
        version_number=new_ver,
        content=content,
        diff_text=diff_text,
        lines_added=added,
        lines_removed=removed,
        commit_message=f"Update {doc.title} (v{new_ver})",
    )
    db.add(ver)

    doc.version_count = new_ver
    doc.source_hash = content_hash
    doc.updated_at = datetime.now(timezone.utc)

    return {"action": "updated", "doc_id": doc.short_id, "version": new_ver, "lines_added": added, "lines_removed": removed, "document": _doc_to_dict(doc)}


# ---- Read ----

async def get_document(db: AsyncSession, user_id: uuid.UUID, short_id: str) -> dict | None:
    doc = (await db.execute(
        select(VersionedDocument).where(
            VersionedDocument.user_id == user_id,
            VersionedDocument.short_id == short_id,
            VersionedDocument.is_active.is_(True),
        )
    )).scalar_one_or_none()
    return _doc_to_dict(doc) if doc else None


async def get_latest_content(db: AsyncSession, user_id: uuid.UUID, short_id: str) -> dict | None:
    doc = await _find_doc(db, user_id, short_id)
    if not doc:
        return None
    ver = (await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.doc_id == doc.id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )).scalar_one_or_none()
    if not ver:
        return None
    return {"doc_id": doc.short_id, "version": ver.version_number, "content": ver.content}


async def get_version_content(
    db: AsyncSession, user_id: uuid.UUID, short_id: str, version: int
) -> dict | None:
    doc = await _find_doc(db, user_id, short_id)
    if not doc:
        return None
    ver = (await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.doc_id == doc.id,
            DocumentVersion.version_number == version,
        )
    )).scalar_one_or_none()
    if not ver:
        return None
    return {"doc_id": doc.short_id, "version": ver.version_number, "content": ver.content}


async def get_history(
    db: AsyncSession, user_id: uuid.UUID, short_id: str, limit: int = 20
) -> list[dict]:
    doc = await _find_doc(db, user_id, short_id)
    if not doc:
        return []
    rows = (await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.doc_id == doc.id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(limit)
    )).scalars().all()
    return [
        {
            "version": v.version_number,
            "message": v.commit_message,
            "lines_added": v.lines_added,
            "lines_removed": v.lines_removed,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in rows
    ]


async def get_diff(
    db: AsyncSession, user_id: uuid.UUID, short_id: str, old_version: int, new_version: int
) -> dict | None:
    doc = await _find_doc(db, user_id, short_id)
    if not doc:
        return None

    old_ver = (await db.execute(
        select(DocumentVersion).where(DocumentVersion.doc_id == doc.id, DocumentVersion.version_number == old_version)
    )).scalar_one_or_none()
    new_ver = (await db.execute(
        select(DocumentVersion).where(DocumentVersion.doc_id == doc.id, DocumentVersion.version_number == new_version)
    )).scalar_one_or_none()

    if not old_ver or not new_ver:
        return None

    diff_text, added, removed = _compute_diff(old_ver.content, new_ver.content)
    return {
        "doc_id": doc.short_id,
        "old_version": old_version,
        "new_version": new_version,
        "diff": diff_text,
        "lines_added": added,
        "lines_removed": removed,
    }


# ---- List / Search ----

async def list_documents(
    db: AsyncSession, user_id: uuid.UUID, project: str | None = None
) -> list[dict]:
    stmt = select(VersionedDocument).where(
        VersionedDocument.user_id == user_id, VersionedDocument.is_active.is_(True)
    )
    if project:
        stmt = stmt.where(VersionedDocument.project == project)
    stmt = stmt.order_by(VersionedDocument.updated_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_doc_to_dict(d) for d in rows]


async def search_documents(
    db: AsyncSession, user_id: uuid.UUID, *, tag: str | None = None, doc_type: str | None = None
) -> list[dict]:
    stmt = select(VersionedDocument).where(
        VersionedDocument.user_id == user_id, VersionedDocument.is_active.is_(True)
    )
    if doc_type:
        stmt = stmt.where(VersionedDocument.doc_type == doc_type)
    rows = (await db.execute(stmt)).scalars().all()
    results = []
    for d in rows:
        if tag and tag not in (d.tags or []):
            continue
        results.append(_doc_to_dict(d))
    return results


async def get_recent(db: AsyncSession, user_id: uuid.UUID, limit: int = 10) -> list[dict]:
    rows = (await db.execute(
        select(VersionedDocument)
        .where(VersionedDocument.user_id == user_id, VersionedDocument.is_active.is_(True))
        .order_by(VersionedDocument.updated_at.desc())
        .limit(limit)
    )).scalars().all()
    return [_doc_to_dict(d) for d in rows]


# ---- Delete ----

async def delete_document(db: AsyncSession, user_id: uuid.UUID, short_id: str) -> bool:
    doc = await _find_doc(db, user_id, short_id)
    if not doc:
        return False
    doc.is_active = False
    return True


# ---- Projects ----

async def list_projects(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = (await db.execute(
        select(DocProject).where(DocProject.user_id == user_id).order_by(DocProject.updated_at.desc())
    )).scalars().all()
    return [{"name": p.name, "description": p.description, "doc_count": p.doc_count, "updated_at": p.updated_at.isoformat() if p.updated_at else None} for p in rows]


async def _ensure_project(db: AsyncSession, user_id: uuid.UUID, project_name: str):
    existing = (await db.execute(
        select(DocProject).where(DocProject.user_id == user_id, DocProject.name == project_name)
    )).scalar_one_or_none()
    if existing:
        existing.doc_count = (await db.execute(
            select(func.count()).select_from(VersionedDocument).where(
                VersionedDocument.user_id == user_id, VersionedDocument.project == project_name, VersionedDocument.is_active.is_(True)
            )
        )).scalar() or 0
    else:
        db.add(DocProject(user_id=user_id, name=project_name, doc_count=1))


# ---- Relationships ----

async def add_relationship(
    db: AsyncSession, user_id: uuid.UUID, project: str,
    from_short_id: str, to_short_id: str, rel_type: str, description: str = ""
) -> dict | None:
    if rel_type not in RELATION_TYPES:
        return None
    from_doc = await _find_doc(db, user_id, from_short_id)
    to_doc = await _find_doc(db, user_id, to_short_id)
    if not from_doc or not to_doc:
        return None
    rel = DocRelationship(
        user_id=user_id, project=project,
        from_doc_id=from_doc.id, to_doc_id=to_doc.id,
        rel_type=rel_type, description=description,
    )
    db.add(rel)
    await db.flush()
    return {"from": from_short_id, "to": to_short_id, "type": rel_type, "description": description}


async def get_relationships(db: AsyncSession, user_id: uuid.UUID, project: str) -> list[dict]:
    rows = (await db.execute(
        select(DocRelationship).where(DocRelationship.user_id == user_id, DocRelationship.project == project)
    )).scalars().all()

    # Resolve short_ids
    result = []
    for r in rows:
        from_doc = (await db.execute(select(VersionedDocument).where(VersionedDocument.id == r.from_doc_id))).scalar_one_or_none()
        to_doc = (await db.execute(select(VersionedDocument).where(VersionedDocument.id == r.to_doc_id))).scalar_one_or_none()
        result.append({
            "from": from_doc.short_id if from_doc else str(r.from_doc_id),
            "to": to_doc.short_id if to_doc else str(r.to_doc_id),
            "type": r.rel_type,
            "description": r.description,
        })
    return result


async def get_impact_chain(
    db: AsyncSession, user_id: uuid.UUID, project: str, short_id: str, max_depth: int = 3
) -> list[dict]:
    """BFS traversal of downstream relationships from a document."""
    doc = await _find_doc(db, user_id, short_id)
    if not doc:
        return []

    visited = {doc.id}
    queue = [(doc.id, 0)]
    impacts = []

    while queue:
        current_id, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        downstream = (await db.execute(
            select(DocRelationship).where(
                DocRelationship.user_id == user_id,
                DocRelationship.project == project,
                DocRelationship.from_doc_id == current_id,
            )
        )).scalars().all()

        for rel in downstream:
            if rel.to_doc_id not in visited:
                visited.add(rel.to_doc_id)
                target = (await db.execute(select(VersionedDocument).where(VersionedDocument.id == rel.to_doc_id))).scalar_one_or_none()
                impacts.append({
                    "doc_id": target.short_id if target else str(rel.to_doc_id),
                    "title": target.title if target else "unknown",
                    "rel_type": rel.rel_type,
                    "depth": depth + 1,
                })
                queue.append((rel.to_doc_id, depth + 1))
    return impacts


# ---- Stats ----

async def get_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
    doc_count = (await db.execute(
        select(func.count()).select_from(VersionedDocument).where(
            VersionedDocument.user_id == user_id, VersionedDocument.is_active.is_(True)
        )
    )).scalar() or 0
    ver_count = (await db.execute(
        select(func.count()).select_from(DocumentVersion)
        .join(VersionedDocument)
        .where(VersionedDocument.user_id == user_id, VersionedDocument.is_active.is_(True))
    )).scalar() or 0
    project_count = (await db.execute(
        select(func.count()).select_from(DocProject).where(DocProject.user_id == user_id)
    )).scalar() or 0
    return {"documents": doc_count, "versions": ver_count, "projects": project_count}


# ---- Helpers ----

async def _find_doc(db: AsyncSession, user_id: uuid.UUID, short_id: str) -> VersionedDocument | None:
    return (await db.execute(
        select(VersionedDocument).where(
            VersionedDocument.user_id == user_id,
            VersionedDocument.short_id == short_id,
            VersionedDocument.is_active.is_(True),
        )
    )).scalar_one_or_none()


def _doc_to_dict(doc: VersionedDocument) -> dict:
    return {
        "doc_id": doc.short_id,
        "title": doc.title,
        "source_file": doc.source_file,
        "project": doc.project,
        "version_count": doc.version_count,
        "doc_type": doc.doc_type,
        "tags": doc.tags,
        "key_entities": doc.key_entities,
        "key_dates": doc.key_dates,
        "summary": doc.summary,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }

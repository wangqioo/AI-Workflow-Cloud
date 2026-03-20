"""Memory service: save, search, consolidate, context injection.

Core of the Mnemosyne system. Handles 4-layer memory management.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..llm.provider import get_llm_provider, strip_think_tags
from ..models.memory import ConversationTurn, CoreMemory, SemanticMemory, SessionSummary
from . import vector


async def save_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    content: str,
    category: str = "fact",
    importance: float = 0.5,
    source_session: str | None = None,
) -> dict:
    """Save a semantic memory entry (L2). Deduplicates via content hash."""
    chash = vector.content_hash(content)

    # Check for duplicate
    result = await db.execute(
        select(SemanticMemory).where(
            SemanticMemory.content_hash == chash,
            SemanticMemory.user_id == user_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.access_count += 1
        existing.last_accessed = datetime.now(timezone.utc)
        await db.flush()
        return {"id": str(existing.id), "deduplicated": True}

    mem = SemanticMemory(
        user_id=user_id,
        content=content,
        category=category,
        importance=importance,
        content_hash=chash,
        source_session=source_session,
    )
    db.add(mem)
    await db.flush()
    await db.refresh(mem)

    # Upsert to Qdrant vector index
    try:
        await vector.upsert_memory(
            str(mem.id),
            content,
            {"user_id": str(user_id), "category": category, "content": content},
        )
    except Exception:
        pass  # Vector index failure is non-fatal

    return {"id": str(mem.id), "deduplicated": False}


async def search_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    top_k: int = 10,
    category: str | None = None,
) -> list[dict]:
    """Semantic search via Qdrant, enriched with DB metadata."""
    try:
        results = await vector.search_memories(query, str(user_id), top_k, category)
    except Exception:
        # Qdrant unavailable — fallback to DB keyword search
        stmt = select(SemanticMemory).where(
            SemanticMemory.user_id == user_id,
            SemanticMemory.content.ilike(f"%{query[:50]}%"),
        ).limit(top_k)
        if category:
            stmt = stmt.where(SemanticMemory.category == category)
        rows = (await db.execute(stmt)).scalars().all()
        results = [
            {"id": str(r.id), "content": r.content, "category": r.category,
             "importance": r.importance, "score": 0.5}
            for r in rows
        ]

    # Bump access_count for returned results
    for r in results:
        await db.execute(
            update(SemanticMemory)
            .where(SemanticMemory.id == uuid.UUID(r["id"]))
            .values(access_count=SemanticMemory.access_count + 1, last_accessed=datetime.now(timezone.utc))
        )

    return results


async def get_context(db: AsyncSession, user_id: uuid.UUID, max_chars: int = 2400) -> str:
    """Assemble memory context for LLM system prompt injection.

    Combines: L3 core memory + L2 top memories + L1 recent summaries.
    """
    parts = []

    # L3: Core memory
    core_rows = (await db.execute(
        select(CoreMemory).where(CoreMemory.user_id == user_id)
    )).scalars().all()
    for cm in core_rows:
        content = cm.content or {}
        if cm.block_type == "user":
            name = content.get("name", "")
            notes = content.get("notes", "")
            if name or notes:
                parts.append(f"[用户] 姓名: {name}")
                if notes:
                    parts.append(f"  备注: {notes}")

    # L2: Top semantic memories (by importance + recency)
    mem_rows = (await db.execute(
        select(SemanticMemory)
        .where(SemanticMemory.user_id == user_id)
        .order_by(SemanticMemory.importance.desc(), SemanticMemory.last_accessed.desc())
        .limit(10)
    )).scalars().all()
    if mem_rows:
        lines = [f"  [{m.category}] {m.content}" for m in mem_rows]
        parts.append("[记忆]\n" + "\n".join(lines))

    # L1: Recent session summaries
    sum_rows = (await db.execute(
        select(SessionSummary)
        .where(SessionSummary.user_id == user_id)
        .order_by(SessionSummary.ended_at.desc())
        .limit(3)
    )).scalars().all()
    if sum_rows:
        lines = [f"  - {s.summary}" for s in sum_rows]
        parts.append("[近期对话摘要]\n" + "\n".join(lines))

    context = "\n".join(parts)
    if len(context) > max_chars:
        context = context[:max_chars] + "\n..."
    return context


async def consolidate(
    db: AsyncSession,
    user_id: uuid.UUID,
    session_id: str,
    messages: list[dict],
) -> dict:
    """Extract long-term memories from conversation via LLM.

    Called at session end (after 3+ user turns).
    """
    # Build conversation text (last 20 turns)
    conv_lines = []
    for m in messages[-20:]:
        role = m.get("role", "?")
        content = m.get("content", "")
        if role in ("user", "assistant") and content:
            conv_lines.append(f"{role}: {content[:500]}")
    conv_text = "\n".join(conv_lines)
    if not conv_text:
        return {"extracted": 0}

    llm = get_llm_provider()

    # Step 1: Extract facts
    extract_prompt = (
        "从以下对话中提取重要的事实和用户偏好，每行一条，格式为:\n"
        "类别|内容\n"
        "类别可以是: preference(偏好), fact(事实), skill(技能), relationship(关系)\n"
        "只输出提取结果。如果没有值得记忆的内容，输出: 无\n\n"
        f"对话:\n{conv_text[:3000]}"
    )

    try:
        resp = await llm.chat(
            [{"role": "user", "content": extract_prompt}],
            max_tokens=500,
            temperature=0.3,
        )
        raw = resp["choices"][0]["message"]["content"]
        raw = strip_think_tags(raw)
    except Exception:
        return {"extracted": 0, "error": "LLM call failed"}

    # Parse and save extracted memories
    extracted = 0
    for line in raw.split("\n"):
        line = line.strip()
        if "|" not in line or line == "无":
            continue
        parts = line.split("|", 1)
        if len(parts) != 2:
            continue
        cat, content = parts[0].strip().lower(), parts[1].strip()
        if len(content) < 4:
            continue
        if cat not in ("preference", "fact", "skill", "relationship"):
            cat = "fact"
        await save_memory(db, user_id, content, category=cat, importance=0.6, source_session=session_id)
        extracted += 1

    # Step 2: Generate session summary
    try:
        summary_resp = await llm.chat(
            [{"role": "user", "content": f"用一句话概括以下对话的主题和结果（中文）:\n{conv_text[:2000]}"}],
            max_tokens=100,
            temperature=0.3,
        )
        summary_text = strip_think_tags(summary_resp["choices"][0]["message"]["content"])
    except Exception:
        summary_text = f"会话包含 {len(messages)} 条消息"

    # Save session summary
    ss = SessionSummary(
        user_id=user_id,
        session_id=session_id,
        summary=summary_text,
        turn_count=sum(1 for m in messages if m.get("role") == "user"),
    )
    db.add(ss)

    return {"extracted": extracted, "summary": summary_text}


async def update_core_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    block_type: str,
    content: dict,
) -> dict:
    """Update core memory block (L3)."""
    result = await db.execute(
        select(CoreMemory).where(
            CoreMemory.user_id == user_id,
            CoreMemory.block_type == block_type,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.content = content
        existing.version += 1
        await db.flush()
        return {"id": str(existing.id), "version": existing.version}

    cm = CoreMemory(user_id=user_id, block_type=block_type, content=content)
    db.add(cm)
    await db.flush()
    await db.refresh(cm)
    return {"id": str(cm.id), "version": 1}

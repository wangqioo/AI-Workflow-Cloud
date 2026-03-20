"""RAG knowledge base service: ingest, query, delete.

Ported from v0.7.5 file-based storage to PostgreSQL + Qdrant.
Reuses embedding infrastructure from memory.vector module.
"""

from __future__ import annotations

import uuid

from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..memory.vector import EMBEDDING_DIM, compute_embedding, get_qdrant
from ..models.rag import Chunk, Document

RAG_COLLECTION = "rag_chunks"
CHUNK_SIZE = 512  # words
CHUNK_OVERLAP = 50  # words


async def ensure_collection():
    """Create the Qdrant collection for RAG if it doesn't exist."""
    client = await get_qdrant()
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if RAG_COLLECTION not in names:
        await client.create_collection(
            collection_name=RAG_COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
    await client.close()


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping word-based chunks."""
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start = end - CHUNK_OVERLAP
    return chunks


async def ingest_text(
    db: AsyncSession,
    user_id: uuid.UUID,
    content: str,
    filename: str = "untitled.txt",
    metadata: dict | None = None,
) -> dict:
    """Ingest a text document: chunk, embed, store in DB + Qdrant."""
    chunks = chunk_text(content)
    if not chunks:
        return {"error": "Empty content"}

    # Create document record
    doc = Document(
        user_id=user_id,
        filename=filename,
        size=len(content.encode()),
        num_chunks=len(chunks),
        metadata_=metadata or {},
    )
    db.add(doc)
    await db.flush()

    # Create chunk records + Qdrant vectors
    qdrant_points = []
    for i, chunk_text_str in enumerate(chunks):
        chunk = Chunk(
            document_id=doc.id,
            user_id=user_id,
            chunk_index=i,
            text=chunk_text_str,
            text_preview=chunk_text_str[:200],
        )
        db.add(chunk)
        await db.flush()

        embedding = await compute_embedding(chunk_text_str)
        qdrant_points.append(
            PointStruct(
                id=str(chunk.id),
                vector=embedding,
                payload={
                    "user_id": str(user_id),
                    "doc_id": str(doc.id),
                    "doc_filename": filename,
                    "chunk_index": i,
                    "text_preview": chunk_text_str[:200],
                },
            )
        )

    # Batch upsert to Qdrant
    if qdrant_points:
        try:
            client = await get_qdrant()
            await client.upsert(collection_name=RAG_COLLECTION, points=qdrant_points)
            await client.close()
        except Exception:
            pass  # Vector index failure is non-fatal

    return {
        "document_id": str(doc.id),
        "filename": filename,
        "num_chunks": len(chunks),
        "size": doc.size,
    }


async def query(
    db: AsyncSession,
    user_id: uuid.UUID,
    query_text: str,
    top_k: int = 5,
) -> list[dict]:
    """Semantic search across user's knowledge base via Qdrant."""
    try:
        query_embedding = await compute_embedding(query_text)
        client = await get_qdrant()
        results = await client.search(
            collection_name=RAG_COLLECTION,
            query_vector=query_embedding,
            query_filter=Filter(must=[
                FieldCondition(key="user_id", match=MatchValue(value=str(user_id))),
            ]),
            limit=top_k,
        )
        await client.close()

        # Enrich with full text from DB
        output = []
        for r in results:
            chunk_id = r.id
            chunk_row = (await db.execute(
                select(Chunk).where(Chunk.id == uuid.UUID(chunk_id))
            )).scalar_one_or_none()

            output.append({
                "chunk_id": chunk_id,
                "doc_id": r.payload.get("doc_id", ""),
                "doc_filename": r.payload.get("doc_filename", ""),
                "chunk_index": r.payload.get("chunk_index", 0),
                "score": round(r.score, 4),
                "text": chunk_row.text if chunk_row else r.payload.get("text_preview", ""),
            })
        return output

    except Exception:
        # Qdrant unavailable — keyword fallback
        query_words = set(query_text.lower().split()[:10])
        stmt = select(Chunk).where(Chunk.user_id == user_id).limit(top_k * 3)
        rows = (await db.execute(stmt)).scalars().all()

        scored = []
        for c in rows:
            chunk_words = set(c.text.lower().split())
            overlap = len(query_words & chunk_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                scored.append((c, score))
        scored.sort(key=lambda x: x[1], reverse=True)

        return [
            {
                "chunk_id": str(c.id),
                "doc_id": str(c.document_id),
                "doc_filename": "",
                "chunk_index": c.chunk_index,
                "score": round(s, 4),
                "text": c.text,
            }
            for c, s in scored[:top_k]
        ]


async def list_documents(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """List all documents for a user."""
    rows = (await db.execute(
        select(Document).where(Document.user_id == user_id).order_by(Document.ingested_at.desc())
    )).scalars().all()
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "size": d.size,
            "num_chunks": d.num_chunks,
            "metadata": d.metadata_,
            "ingested_at": d.ingested_at.isoformat() if d.ingested_at else None,
        }
        for d in rows
    ]


async def delete_document(db: AsyncSession, user_id: uuid.UUID, doc_id: uuid.UUID) -> bool:
    """Delete a document and its chunks from DB + Qdrant."""
    doc = (await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user_id)
    )).scalar_one_or_none()
    if not doc:
        return False

    # Get chunk IDs for Qdrant cleanup
    chunks = (await db.execute(
        select(Chunk.id).where(Chunk.document_id == doc_id)
    )).scalars().all()

    # Delete from Qdrant
    if chunks:
        try:
            client = await get_qdrant()
            await client.delete(
                collection_name=RAG_COLLECTION,
                points_selector=[str(cid) for cid in chunks],
            )
            await client.close()
        except Exception:
            pass

    # Delete from DB (cascades to chunks)
    await db.delete(doc)
    return True


async def get_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Get knowledge base statistics."""
    doc_count = (await db.execute(
        select(func.count()).select_from(Document).where(Document.user_id == user_id)
    )).scalar() or 0
    chunk_count = (await db.execute(
        select(func.count()).select_from(Chunk).where(Chunk.user_id == user_id)
    )).scalar() or 0
    total_size = (await db.execute(
        select(func.sum(Document.size)).where(Document.user_id == user_id)
    )).scalar() or 0

    return {
        "num_documents": doc_count,
        "num_chunks": chunk_count,
        "total_size": total_size,
    }

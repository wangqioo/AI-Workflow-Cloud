"""Vector search via Qdrant for semantic memory retrieval.

Replaces v0.7.5's brute-force cosine search on SQLite BLOBs.
Embeddings generated via LLM provider's embedding API (OpenAI-compatible).
"""

from __future__ import annotations

import hashlib
from typing import Any

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from ..config import settings

COLLECTION_NAME = "semantic_memory"
EMBEDDING_DIM = 1024  # Qwen embedding dimension (adjustable)


async def get_qdrant() -> AsyncQdrantClient:
    return AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


async def ensure_collection():
    """Create the collection if it doesn't exist."""
    client = await get_qdrant()
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if COLLECTION_NAME not in names:
        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
    await client.close()


async def compute_embedding(text: str) -> list[float]:
    """Generate embedding via LLM provider's embedding endpoint.

    Falls back to hash-based embedding if API unavailable.
    """
    # Try Qwen embedding API first
    if settings.qwen_api_key:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{settings.qwen_base_url}/embeddings",
                    json={"model": "text-embedding-v3", "input": text, "dimensions": EMBEDDING_DIM},
                    headers={"Authorization": f"Bearer {settings.qwen_api_key}"},
                )
                resp.raise_for_status()
                return resp.json()["data"][0]["embedding"]
        except Exception:
            pass

    # Try OpenAI embedding API
    if settings.openai_api_key:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{settings.openai_base_url}/embeddings",
                    json={"model": "text-embedding-3-small", "input": text},
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()["data"][0]["embedding"]
                return data[:EMBEDDING_DIM]  # Truncate to expected dim
        except Exception:
            pass

    # Hash-based fallback (deterministic, no API needed)
    return _hash_embedding(text)


def _hash_embedding(text: str) -> list[float]:
    """Hash-based embedding fallback (same logic as v0.7.5)."""
    vec = [0.0] * EMBEDDING_DIM
    tokens = list(text.lower())
    # Add bigrams
    for i in range(len(tokens) - 1):
        tokens.append(tokens[i] + tokens[i + 1])

    for token in tokens:
        h = hashlib.md5(token.encode()).hexdigest()
        idx = int(h[:8], 16) % EMBEDDING_DIM
        sign = 1.0 if int(h[8:10], 16) > 127 else -1.0
        vec[idx] += sign

    # L2 normalize
    norm = sum(x * x for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def content_hash(text: str) -> str:
    """SHA-256 content hash for deduplication."""
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()[:32]


async def upsert_memory(memory_id: str, text: str, metadata: dict[str, Any]):
    """Insert or update a memory vector in Qdrant."""
    embedding = await compute_embedding(text)
    client = await get_qdrant()
    await client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=memory_id,
                vector=embedding,
                payload=metadata,
            )
        ],
    )
    await client.close()


async def search_memories(
    query: str, user_id: str, top_k: int = 10, category: str | None = None
) -> list[dict]:
    """Semantic search in Qdrant."""
    embedding = await compute_embedding(query)
    client = await get_qdrant()

    filters = {"must": [{"key": "user_id", "match": {"value": user_id}}]}
    if category:
        filters["must"].append({"key": "category", "match": {"value": category}})

    from qdrant_client.models import Filter, FieldCondition, MatchValue

    conditions = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
    if category:
        conditions.append(FieldCondition(key="category", match=MatchValue(value=category)))

    results = await client.search(
        collection_name=COLLECTION_NAME,
        query_vector=embedding,
        query_filter=Filter(must=conditions),
        limit=top_k,
    )
    await client.close()

    return [
        {
            "id": str(r.id),
            "score": round(r.score, 4),
            **r.payload,
        }
        for r in results
    ]


async def delete_memory(memory_id: str):
    """Delete a memory vector from Qdrant."""
    client = await get_qdrant()
    await client.delete(collection_name=COLLECTION_NAME, points_selector=[memory_id])
    await client.close()

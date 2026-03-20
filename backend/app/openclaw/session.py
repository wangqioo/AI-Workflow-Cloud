"""Session management for OpenClaw agent conversations.

v0.7.5 used in-memory dict (lost on restart).
v0.8 uses Redis for persistence across restarts and horizontal scaling.
Falls back to in-memory dict if Redis unavailable.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import redis.asyncio as aioredis

from ..config import settings

MAX_MESSAGES = 40
SESSION_TTL = 86400 * 7  # 7 days


class Session:
    def __init__(self, session_id: str, system_prompt: str):
        self.session_id = session_id
        self.messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        self.created_at = time.time()
        self.turn_count = 0

    def add_message(self, role: str, content: str, **kwargs):
        msg = {"role": role, "content": content, **kwargs}
        self.messages.append(msg)
        if role == "user":
            self.turn_count += 1
        # Keep system prompt + last MAX_MESSAGES
        if len(self.messages) > MAX_MESSAGES + 1:
            self.messages = [self.messages[0]] + self.messages[-(MAX_MESSAGES):]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "created_at": self.created_at,
            "turn_count": self.turn_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Session:
        s = cls.__new__(cls)
        s.session_id = data["session_id"]
        s.messages = data["messages"]
        s.created_at = data["created_at"]
        s.turn_count = data.get("turn_count", 0)
        return s


class SessionStore:
    """Redis-backed session store with in-memory fallback."""

    def __init__(self):
        self._redis: aioredis.Redis | None = None
        self._memory: dict[str, Session] = {}

    async def _get_redis(self) -> aioredis.Redis | None:
        if self._redis is not None:
            return self._redis
        try:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            await self._redis.ping()
            return self._redis
        except Exception:
            self._redis = None
            return None

    def _key(self, session_id: str) -> str:
        return f"openclaw:session:{session_id}"

    async def get_or_create(self, session_id: str | None, system_prompt: str) -> Session:
        sid = session_id or str(uuid.uuid4())

        # Try Redis first
        r = await self._get_redis()
        if r:
            data = await r.get(self._key(sid))
            if data:
                session = Session.from_dict(json.loads(data))
                # Update system prompt if changed
                session.messages[0]["content"] = system_prompt
                return session
        elif sid in self._memory:
            session = self._memory[sid]
            session.messages[0]["content"] = system_prompt
            return session

        return Session(sid, system_prompt)

    async def save(self, session: Session):
        r = await self._get_redis()
        if r:
            await r.set(self._key(session.session_id), json.dumps(session.to_dict()), ex=SESSION_TTL)
        else:
            self._memory[session.session_id] = session

    async def delete(self, session_id: str):
        r = await self._get_redis()
        if r:
            await r.delete(self._key(session_id))
        self._memory.pop(session_id, None)

    async def list_sessions(self, prefix: str = "") -> list[dict[str, Any]]:
        sessions = []
        r = await self._get_redis()
        if r:
            pattern = f"openclaw:session:{prefix}*"
            async for key in r.scan_iter(match=pattern, count=100):
                data = await r.get(key)
                if data:
                    d = json.loads(data)
                    sessions.append({
                        "session_id": d["session_id"],
                        "message_count": len(d["messages"]),
                        "created_at": d["created_at"],
                    })
        else:
            for s in self._memory.values():
                if s.session_id.startswith(prefix):
                    sessions.append({
                        "session_id": s.session_id,
                        "message_count": len(s.messages),
                        "created_at": s.created_at,
                    })
        return sessions


# Singleton
_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store

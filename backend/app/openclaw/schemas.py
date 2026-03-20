"""OpenClaw request/response schemas."""

from pydantic import BaseModel


class AgentChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    provider: str | None = None
    model: str | None = None


class AgentChatResponse(BaseModel):
    response: str
    session_id: str
    tool_calls: list[dict] | None = None


class SessionInfo(BaseModel):
    session_id: str
    message_count: int
    created_at: str

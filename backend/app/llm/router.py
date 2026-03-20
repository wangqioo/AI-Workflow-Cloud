"""LLM API endpoints: chat, stream, list providers."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..auth.dependencies import get_current_user
from ..models.user import User
from .provider import get_llm_provider

router = APIRouter(prefix="/api/llm", tags=["llm"])


class ChatRequest(BaseModel):
    messages: list[dict]
    provider: str | None = None
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False
    tools: list[dict] | None = None


@router.get("/providers")
async def list_providers(user: User = Depends(get_current_user)):
    llm = get_llm_provider()
    return {"providers": llm.list_providers()}


@router.post("/chat")
async def chat(body: ChatRequest, user: User = Depends(get_current_user)):
    llm = get_llm_provider()

    if body.stream:
        return StreamingResponse(
            llm.chat_stream(
                body.messages,
                provider=body.provider,
                model=body.model,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
                tools=body.tools,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    result = await llm.chat(
        body.messages,
        provider=body.provider,
        model=body.model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        tools=body.tools,
    )
    return result

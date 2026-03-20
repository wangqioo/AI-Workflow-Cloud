"""OpenClaw Agent API endpoints: chat, stream, sessions."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..auth.dependencies import get_current_user
from ..models.user import User
from .agent import run_agent, stream_agent
from .schemas import AgentChatRequest
from .session import get_session_store

router = APIRouter(prefix="/api/agents", tags=["openclaw"])


@router.post("/run")
async def agent_run(body: AgentChatRequest, user: User = Depends(get_current_user)):
    """Non-streaming agent execution."""
    result = await run_agent(
        message=body.message,
        session_id=body.session_id,
        provider=body.provider,
        model=body.model,
        user_id=str(user.id),
    )
    return result


@router.post("/stream")
async def agent_stream(body: AgentChatRequest, user: User = Depends(get_current_user)):
    """SSE streaming agent execution."""
    return StreamingResponse(
        stream_agent(
            message=body.message,
            session_id=body.session_id,
            provider=body.provider,
            model=body.model,
            user_id=str(user.id),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions")
async def list_sessions(user: User = Depends(get_current_user)):
    """List active sessions for current user."""
    store = get_session_store()
    sessions = await store.list_sessions(prefix=str(user.id))
    return {"sessions": sessions}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: User = Depends(get_current_user)):
    """Delete a session."""
    store = get_session_store()
    await store.delete(session_id)
    return {"status": "deleted"}

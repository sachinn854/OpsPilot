"""
Chat endpoint: POST /v1/chat

Ties the whole chat pipeline together:
  load history → run Copilot (LLM + tools) → persist messages → return reply.

Memory is the conversation history stored in Postgres. Pass back the returned
`conversation_id` on the next request to continue the same conversation.
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from functools import lru_cache

from backend.agents.copilot import CopilotAgent
from backend.api.deps import get_registry, limiter
from backend.config import settings
from backend.db.models import Conversation, Message
from backend.db.session import AsyncSessionLocal, get_session
from backend.llm.openrouter_provider import OpenRouterProvider
from backend.security.guardrails import check_injection

router = APIRouter(prefix="/v1", tags=["chat"])

_MAX_HISTORY = 40  # max messages loaded from DB per conversation


@lru_cache(maxsize=1)
def _get_copilot() -> CopilotAgent:
    """Lazy singleton — created on first request, not at import time."""
    from backend.core.tool_router import build_default_router
    return CopilotAgent(llm=OpenRouterProvider(), router=build_default_router())


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def chat(
    request: Request,
    req: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    guard = check_injection(req.message)
    if not guard.safe:
        raise HTTPException(status_code=400, detail=guard.reason)

    # Load or create the conversation.
    if req.conversation_id:
        conversation = await session.get(Conversation, req.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="conversation not found")
    else:
        conversation = Conversation(title=req.message[:50])
        session.add(conversation)
        await session.flush()  # assigns conversation.id

    # Load prior history (the agent's memory) — cap to avoid burning context window.
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(_MAX_HISTORY)
    )
    history = [{"role": m.role, "content": m.content} for m in reversed(result.scalars().all())]

    # Append the new user turn (both for the agent and for storage).
    history.append({"role": "user", "content": req.message})
    session.add(
        Message(conversation_id=conversation.id, role="user", content=req.message)
    )

    # Run the Copilot.
    try:
        reply = await _get_copilot().run(history)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Persist the assistant reply.
    session.add(
        Message(conversation_id=conversation.id, role="assistant", content=reply)
    )
    await session.commit()

    return ChatResponse(conversation_id=conversation.id, reply=reply)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def chat_stream(
    request: Request,
    req: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    guard = check_injection(req.message)
    if not guard.safe:
        raise HTTPException(status_code=400, detail=guard.reason)

    # Load or create the conversation.
    if req.conversation_id:
        conversation = await session.get(Conversation, req.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="conversation not found")
    else:
        conversation = Conversation(title=req.message[:50])
        session.add(conversation)
        await session.flush()

    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(_MAX_HISTORY)
    )
    history = [{"role": m.role, "content": m.content} for m in reversed(result.scalars().all())]
    history.append({"role": "user", "content": req.message})

    session.add(
        Message(conversation_id=conversation.id, role="user", content=req.message)
    )
    # Commit everything (conversation + user message) NOW so the generator
    # can open a fresh session later without hitting FK violations.
    await session.commit()
    conv_id = conversation.id

    async def event_stream():
        yield _sse({"event": "start", "conversation_id": conv_id})
        final_text = ""
        try:
            async for ev in _get_copilot().run_stream(history):
                if ev["type"] == "tool":
                    yield _sse({"event": "tool", "name": ev["name"]})
                elif ev["type"] == "token":
                    yield _sse({"event": "token", "text": ev["text"]})
                elif ev["type"] == "done":
                    final_text = ev["text"]
        except Exception as exc:  # noqa: BLE001
            yield _sse({"event": "error", "detail": str(exc)})
            return

        # Use a fresh session — the request-scoped dependency session is gone
        # by the time this generator resumes after streaming completes.
        async with AsyncSessionLocal() as new_session:
            new_session.add(
                Message(conversation_id=conv_id, role="assistant", content=final_text)
            )
            await new_session.commit()
        yield _sse({"event": "done", "conversation_id": conv_id})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

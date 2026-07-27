"""
Chat endpoint: POST /v1/chat

Ties the whole chat pipeline together:
  load history → run Copilot (LLM + tools) → persist messages → return reply.

Memory is the conversation history stored in Postgres. Pass back the returned
`conversation_id` on the next request to continue the same conversation.
"""
import asyncio
import json

import httpx

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.copilot import CopilotAgent
from backend.api.deps import limiter
from backend.auth.deps import get_current_user
from backend.config import settings
from backend.db.models import Conversation, Message, User
from backend.db.session import AsyncSessionLocal, get_session
from backend.llm.factory import get_llm_for_user
from backend.security.guardrails import check_injection

router = APIRouter(prefix="/v1", tags=["chat"])

_MAX_HISTORY = 40


async def _auto_title(conv_id: str, user_msg: str, reply: str) -> None:
    """Generate a smart title for a new conversation using a free small model."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.CLASSIFIER_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": (
                            "Write a short 4-6 word title for this conversation. "
                            "No quotes, no punctuation at end. Return only the title.\n"
                            f"User: {user_msg[:200]}\n"
                            f"Reply: {reply[:300]}"
                        ),
                    }],
                    "max_tokens": 20,
                    "temperature": 0.3,
                },
            )
        resp.raise_for_status()
        title = (resp.json()["choices"][0]["message"]["content"] or "").strip().strip('"\'').strip()[:80]
        if not title:
            return
        async with AsyncSessionLocal() as s:
            conv = await s.get(Conversation, conv_id)
            if conv:
                conv.title = title
                await s.commit()
    except Exception:
        pass


_WEEKLY_FREE_LIMIT = 6
_WEEK_TTL = 7 * 24 * 3600  # 604800 seconds


def _get_router():
    from backend.core.tool_router import build_default_router
    return build_default_router()


async def _enforce_weekly_limit(user_id: str) -> None:
    """Check + increment the weekly free-tier counter. Raises 429 when exhausted."""
    import redis.asyncio as aioredis
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    key = f"chat_weekly:{user_id}"
    try:
        count = int(await r.get(key) or 0)
        if count >= _WEEKLY_FREE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"You've used all {_WEEKLY_FREE_LIMIT} free messages for this week. "
                    "Go to Settings → LLM Provider and add your own OpenRouter API key "
                    "to get unlimited messages."
                ),
            )
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, _WEEK_TTL)
        await pipe.execute()
    except HTTPException:
        raise
    except Exception:
        pass  # Redis unavailable → allow the request
    finally:
        try:
            await r.aclose()
        except Exception:
            pass


async def _resolve_api_key(user, session) -> str | None:
    """
    Return the OpenRouter API key to use for this user:
      1. User's own saved key (no weekly limit)
      2. Server env key (enforces _WEEKLY_FREE_LIMIT per user per week)
      3. None (Ollama / no key configured)
    Raises HTTPException if no key is available at all.
    """
    from backend.integrations.store import get_token

    provider = (getattr(user, "llm_provider", "") or settings.LLM_PROVIDER).lower()
    if provider == "ollama":
        return None

    own_key = await get_token(session, org_id=str(user.id), service="openrouter")
    if own_key:
        return own_key

    if settings.OPENROUTER_API_KEY:
        await _enforce_weekly_limit(str(user.id))
        return settings.OPENROUTER_API_KEY

    raise HTTPException(
        status_code=400,
        detail=(
            "No OpenRouter API key configured. "
            "Go to Settings → LLM Provider and add your key."
        ),
    )


async def _get_copilot(user, session) -> CopilotAgent:
    api_key = await _resolve_api_key(user, session)
    return CopilotAgent(llm=get_llm_for_user(user, api_key=api_key), router=_get_router())


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
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    guard = check_injection(req.message)
    if not guard.safe:
        raise HTTPException(status_code=400, detail=guard.reason)

    is_new = not req.conversation_id
    if req.conversation_id:
        conversation = await session.get(Conversation, req.conversation_id)
        if conversation is None or conversation.org_id != current_user.id:
            raise HTTPException(status_code=404, detail="conversation not found")
    else:
        conversation = Conversation(org_id=current_user.id, title=req.message[:50])
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
    session.add(Message(conversation_id=conversation.id, role="user", content=req.message))

    try:
        reply = await (await _get_copilot(current_user, session)).run(history, user_name=current_user.name or current_user.email)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    session.add(Message(conversation_id=conversation.id, role="assistant", content=reply))
    await session.commit()

    if is_new:
        background_tasks.add_task(_auto_title, conversation.id, req.message, reply)

    return ChatResponse(conversation_id=conversation.id, reply=reply)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def chat_stream(
    request: Request,
    req: ChatRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    guard = check_injection(req.message)
    if not guard.safe:
        raise HTTPException(status_code=400, detail=guard.reason)

    is_new = not req.conversation_id
    if req.conversation_id:
        conversation = await session.get(Conversation, req.conversation_id)
        if conversation is None or conversation.org_id != current_user.id:
            raise HTTPException(status_code=404, detail="conversation not found")
    else:
        conversation = Conversation(org_id=current_user.id, title=req.message[:50])
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

    user_api_key = await _resolve_api_key(current_user, session)

    session.add(Message(conversation_id=conversation.id, role="user", content=req.message))
    await session.commit()
    conv_id  = conversation.id
    user_msg = req.message
    copilot  = CopilotAgent(llm=get_llm_for_user(current_user, api_key=user_api_key), router=_get_router())

    async def event_stream():
        yield _sse({"event": "start", "conversation_id": conv_id})
        final_text = ""
        try:
            async for ev in copilot.run_stream(history, user_name=current_user.name or current_user.email):
                if ev["type"] == "tool":
                    yield _sse({"event": "tool", "name": ev["name"]})
                elif ev["type"] == "token":
                    yield _sse({"event": "token", "text": ev["text"]})
                elif ev["type"] == "done":
                    final_text = ev["text"]
        except Exception as exc:  # noqa: BLE001
            yield _sse({"event": "error", "detail": str(exc)})
            return

        async with AsyncSessionLocal() as new_session:
            new_session.add(Message(conversation_id=conv_id, role="assistant", content=final_text))
            await new_session.commit()

        if is_new:
            asyncio.create_task(_auto_title(conv_id, user_msg, final_text))

        yield _sse({"event": "done", "conversation_id": conv_id})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

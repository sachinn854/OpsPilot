"""
Chat endpoint: POST /v1/chat

Ties the whole chat pipeline together:
  load history → run Copilot (LLM + tools) → persist messages → return reply.

Memory is the conversation history stored in Postgres. Pass back the returned
`conversation_id` on the next request to continue the same conversation.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.copilot import CopilotAgent
from backend.api.deps import limiter
from backend.config import settings
from backend.core.tool_router import ToolRouter
from backend.db.models import Conversation, Message
from backend.db.session import get_session
from backend.llm.groq_provider import GroqProvider
from backend.security.guardrails import check_injection
from backend.tools.github import GitHubCommitsTool, GitHubIssuesTool
from backend.tools.rag import RagSearchTool

router = APIRouter(prefix="/v1", tags=["chat"])

# Build the Copilot once at import time (cheap singletons).
_tool_router = ToolRouter(
    [GitHubIssuesTool(), GitHubCommitsTool(), RagSearchTool()]
)
_copilot = CopilotAgent(llm=GroqProvider(), router=_tool_router)


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

    # Load prior history (the agent's memory).
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    )
    history = [{"role": m.role, "content": m.content} for m in result.scalars().all()]

    # Append the new user turn (both for the agent and for storage).
    history.append({"role": "user", "content": req.message})
    session.add(
        Message(conversation_id=conversation.id, role="user", content=req.message)
    )

    # Run the Copilot.
    try:
        reply = await _copilot.run(history)
    except RuntimeError as exc:  # e.g. missing GROQ_API_KEY
        raise HTTPException(status_code=503, detail=str(exc))

    # Persist the assistant reply.
    session.add(
        Message(conversation_id=conversation.id, role="assistant", content=reply)
    )
    await session.commit()

    return ChatResponse(conversation_id=conversation.id, reply=reply)

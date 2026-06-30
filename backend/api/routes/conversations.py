"""
Conversations CRUD — list, fetch messages, delete.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.deps import get_current_user
from backend.db.models import Conversation, Message, User
from backend.db.session import get_session

router = APIRouter(prefix="/v1", tags=["conversations"])


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    msg_count: int
    last_active: str | None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(
            Conversation,
            func.count(Message.id).label("msg_count"),
            func.max(Message.created_at).label("last_active"),
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.org_id == current_user.id)
        .group_by(Conversation.id)
        .order_by(
            func.coalesce(func.max(Message.created_at), Conversation.created_at).desc()
        )
        .limit(min(limit, 200))
    )
    rows = (await session.execute(stmt)).all()
    return [
        ConversationOut(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at.isoformat(),
            msg_count=msg_count or 0,
            last_active=last_active.isoformat() if last_active else None,
        )
        for conv, msg_count, last_active in rows
    ]


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
async def get_conversation_messages(
    conv_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    conv = await session.get(Conversation, conv_id)
    if not conv or conv.org_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    return [
        MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at.isoformat())
        for m in result.scalars().all()
    ]


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    conv = await session.get(Conversation, conv_id)
    if not conv or conv.org_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await session.delete(conv)
    await session.commit()
    return {"deleted": conv_id}

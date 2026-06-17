"""
Database models (Phase 1): conversations and messages.

These back the Copilot's basic memory — the conversation history that gets loaded
on each request so the agent has context. More tables (runs, tool_calls,
approvals, documents, memories) are added in later phases per ARCHITECTURE.md §8.

Note: every table carries `org_id` for multi-tenancy (CLAUDE.md rule). The
`organizations` table itself arrives with auth in a later phase; for now we
default to "default".
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.session import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    title: Mapped[str] = mapped_column(String(255), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        order_by="Message.created_at",
        cascade="all, delete-orphan",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # user | assistant | system | tool
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


# ---------------------------------------------------------------------------
# Phase 2 — RAG knowledge base.
#
# A `Document` is one uploaded file. It is split into `DocumentChunk`s; each
# chunk's embedding lives in Qdrant (keyed by `point_id`), while the chunk text
# and metadata stay here in Postgres for citations and durability.
# ---------------------------------------------------------------------------
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    filename: Mapped[str] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(512), default="upload")
    num_chunks: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        order_by="DocumentChunk.chunk_index",
        cascade="all, delete-orphan",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    org_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    chunk_index: Mapped[int] = mapped_column()
    content: Mapped[str] = mapped_column(Text)
    point_id: Mapped[str] = mapped_column(String(64), index=True)  # Qdrant point id
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")


# ---------------------------------------------------------------------------
# Phase 3 — Multi-agent runs.
#
# A `Run` is one goal driven through the LangGraph flow
# (Planner → Research → Execution → Critic → Reporting). Every tool the
# Execution agent calls is logged as a `ToolCallRecord` for traceability.
# Structured payloads (plan, sources) are stored as JSON text for durability.
# ---------------------------------------------------------------------------
class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="running"
    )  # running | completed | failed
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tool_calls: Mapped[list["ToolCallRecord"]] = relationship(
        back_populates="run",
        order_by="ToolCallRecord.created_at",
        cascade="all, delete-orphan",
    )


class ToolCallRecord(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    org_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    tool_name: Mapped[str] = mapped_column(String(128))
    arguments: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped["Run"] = relationship(back_populates="tool_calls")

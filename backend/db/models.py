"""
Database models: conversations and messages.

These back the Copilot's basic memory — the conversation history that gets loaded
on each request so the agent has context. More tables (runs, tool_calls,
approvals, documents, memories) are added as the system grows.

Note: every table carries `org_id` for multi-tenancy. The
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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.session import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Digest email preferences
    digest_email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    digest_email_override: Mapped[str] = mapped_column(String(255), default="")
    # LLM provider preference (overrides .env when set)
    llm_provider: Mapped[str] = mapped_column(String(50), default="")   # "" = use env default
    llm_model: Mapped[str] = mapped_column(String(255), default="")     # "" = use env default


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
# RAG knowledge base.
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
# Multi-agent runs.
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
        String(20), default="running", index=True
    )  # running | completed | failed | awaiting_approval
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


# ---------------------------------------------------------------------------
# Human-in-the-loop approvals.
#
# When the Security agent flags a sensitive action, the run PAUSES (LangGraph
# interrupt) and an `Approval` row is created (status=pending). A human approves
# or rejects it; the decision resumes the run. Together `tool_calls` + `approvals`
# form the audit trail.
# ---------------------------------------------------------------------------
class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    org_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    action: Mapped[str] = mapped_column(String(255))  # short label, e.g. "rollback"
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | approved | rejected
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Integration tokens.
#
# Each org can connect external services (GitHub, Slack, Jira, etc.) by storing
# an encrypted token here. Tools fetch the token for the current org instead of
# reading from .env, enabling per-user/per-org credentials.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# GitHub / external webhook events.
#
# Every inbound webhook is persisted raw before any processing so we have a
# full audit trail and can replay events. A Celery task picks up the event_id
# and does the actual work asynchronously.
# ---------------------------------------------------------------------------
class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    source: Mapped[str] = mapped_column(String(32))          # github | slack | ...
    event_type: Mapped[str] = mapped_column(String(64))      # push | pull_request | issues | release
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)  # opened | closed | ...
    delivery_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # X-GitHub-Delivery
    payload: Mapped[str] = mapped_column(Text)               # raw JSON
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class IntegrationToken(Base):
    __tablename__ = "integration_tokens"
    __table_args__ = (
        UniqueConstraint("org_id", "service", name="uq_integration_org_service"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    service: Mapped[str] = mapped_column(String(64))   # github | slack | jira | linear
    token_encrypted: Mapped[str] = mapped_column(Text)  # Fernet-encrypted token
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON (username, workspace, etc.)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SlackKeywordAlert(Base):
    """A keyword to watch across Slack channels — fires email/DM when matched."""
    __tablename__ = "slack_keyword_alerts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    keyword: Mapped[str] = mapped_column(String(255))
    # Comma-separated channel names to watch; empty string = all channels
    channels: Mapped[str] = mapped_column(String(1024), default="")
    # "email" | "dm" | "both"
    notify_via: Mapped[str] = mapped_column(String(16), default="both")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SlackEventTrigger(Base):
    """An event trigger: when a Slack message matches, run an automatic action."""
    __tablename__ = "slack_event_triggers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    name: Mapped[str] = mapped_column(String(255))
    trigger_keyword: Mapped[str] = mapped_column(String(255))
    # Channel to watch; empty = all channels
    source_channel: Mapped[str] = mapped_column(String(255), default="")
    # "create_github_issue" | "post_to_channel" | "run_copilot"
    action_type: Mapped[str] = mapped_column(String(64))
    # JSON-encoded config for the action (repo, target_channel, prompt, etc.)
    action_config: Mapped[str] = mapped_column(Text, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

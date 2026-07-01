"""
Documents endpoints: ingest files and ask grounded questions.

  POST /v1/documents        → upload a file → chunk + embed + store
  POST /v1/documents/ask    → ask a question → cited answer from the documents
  GET  /v1/documents        → list ingested documents
"""
import pathlib

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_registry, limiter
from backend.auth.deps import get_current_user
from backend.config import settings
from backend.db.models import Document, User
from backend.db.session import get_session
from backend.llm.openrouter_provider import OpenRouterProvider
from backend.rag.extract import extract_text
from backend.rag.ingest import ingest_text
from backend.rag.pipeline import RagAnswer, answer_question
from backend.security.guardrails import check_injection
from backend.security.rbac import Role, require_role

router = APIRouter(prefix="/v1/documents", tags=["documents"])
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
_ALLOWED_SUFFIXES = {".txt", ".md", ".pdf", ".py", ".js", ".ts", ".json"}
_llm = OpenRouterProvider()


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    num_chunks: int


class AskRequest(BaseModel):
    question: str
    top_k: int | None = None


class DocumentInfo(BaseModel):
    id: str
    filename: str
    source: str
    num_chunks: int


@router.post("", response_model=UploadResponse)
@limiter.limit("5/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _role: Role = require_role(Role.operator),
    user: User = Depends(get_current_user),
) -> UploadResponse:
    # Sanitise filename — strip any path components.
    safe_name = pathlib.Path(file.filename or "upload.bin").name
    suffix = pathlib.Path(safe_name).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(_ALLOWED_SUFFIXES)}",
        )

    # Enforce file size limit before reading into memory.
    raw = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed: {_MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file.")

    try:
        text = extract_text(safe_name, raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not text.strip():
        raise HTTPException(status_code=400, detail="No extractable text in the file.")

    try:
        doc = await ingest_text(session, text=text, filename=safe_name, org_id=str(user.id))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ingestion failed: {exc}")

    return UploadResponse(document_id=doc.id, filename=doc.filename, num_chunks=doc.num_chunks)


@router.post("/ask", response_model=RagAnswer)
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def ask(
    request: Request,
    req: AskRequest,
    _role: Role = require_role(Role.viewer),
    user: User = Depends(get_current_user),
) -> RagAnswer:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")

    guard = check_injection(req.question)
    if not guard.safe:
        raise HTTPException(status_code=400, detail=guard.reason)

    try:
        return await answer_question(req.question, llm=_llm, org_id=str(user.id), top_k=req.top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("", response_model=list[DocumentInfo])
@limiter.limit("30/minute")
async def list_documents(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[DocumentInfo]:
    result = await session.execute(
        select(Document).where(Document.org_id == str(user.id)).order_by(Document.created_at)
    )
    return [
        DocumentInfo(id=d.id, filename=d.filename, source=d.source, num_chunks=d.num_chunks)
        for d in result.scalars().all()
    ]

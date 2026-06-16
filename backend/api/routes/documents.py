"""
Documents endpoints (Phase 2): ingest files and ask grounded questions.

  POST /v1/documents        → upload a file (.txt/.md/.pdf) → chunk + embed + store
  POST /v1/documents/ask    → ask a question → cited answer from the documents
  GET  /v1/documents        → list ingested documents

Memory/auth come later; for now everything is scoped to org_id="default".
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Document
from backend.db.session import get_session
from backend.llm.groq_provider import GroqProvider
from backend.rag.extract import extract_text
from backend.rag.ingest import ingest_text
from backend.rag.pipeline import RagAnswer, answer_question

router = APIRouter(prefix="/v1/documents", tags=["documents"])

_ORG = "default"
_llm = GroqProvider()


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
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file.")

    try:
        text = extract_text(file.filename or "upload.txt", raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not text.strip():
        raise HTTPException(
            status_code=400, detail="No extractable text in the file."
        )

    try:
        doc = await ingest_text(
            session, text=text, filename=file.filename or "upload.txt", org_id=_ORG
        )
    except Exception as exc:  # embeddings/Qdrant errors
        raise HTTPException(status_code=503, detail=f"Ingestion failed: {exc}")

    return UploadResponse(
        document_id=doc.id, filename=doc.filename, num_chunks=doc.num_chunks
    )


@router.post("/ask", response_model=RagAnswer)
async def ask(req: AskRequest) -> RagAnswer:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")
    try:
        return await answer_question(
            req.question, llm=_llm, org_id=_ORG, top_k=req.top_k
        )
    except RuntimeError as exc:  # missing GROQ_API_KEY
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("", response_model=list[DocumentInfo])
async def list_documents(
    session: AsyncSession = Depends(get_session),
) -> list[DocumentInfo]:
    result = await session.execute(
        select(Document).where(Document.org_id == _ORG).order_by(Document.created_at)
    )
    return [
        DocumentInfo(
            id=d.id, filename=d.filename, source=d.source, num_chunks=d.num_chunks
        )
        for d in result.scalars().all()
    ]

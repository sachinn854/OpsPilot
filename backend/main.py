"""
AI Operations Copilot — FastAPI application entrypoint.

Run locally:
    uvicorn backend.main:app --reload

The /v1/chat endpoint (single Copilot agent + GitHub tools +
conversation memory). Tables are created on startup for convenience; Alembic
migrations replace this in a later phase.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import approvals, chat, documents, runs
from backend.config import settings

logger = logging.getLogger("copilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Best-effort DB init — the app still boots (and /health works) if the
    # database isn't running yet, so setup is forgiving.
    try:
        from backend.db.session import init_db

        await init_db()
        logger.info("Database initialized.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB init skipped/failed (is docker-compose up?): %s", exc)
    yield


app = FastAPI(
    title="AI Operations Copilot",
    description="Autonomous enterprise AI assistant — plans, retrieves, reasons, and acts.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the React frontend (added later) to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(runs.router)
app.include_router(approvals.router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    """Liveness check — confirms the API is up."""
    return {
        "status": "ok",
        "app": "ai-operations-copilot",
        "env": settings.APP_ENV,
        "version": app.version,
    }


@app.get("/", tags=["system"])
async def root() -> dict:
    """Friendly root pointing to the docs."""
    return {"message": "AI Operations Copilot API. See /docs for the API explorer."}

<div align="center">

# OpsPilot

### Autonomous AI Operations Copilot

*Give it a goal. It plans, researches, executes, verifies — and asks before it acts.*

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Railway-6366f1?style=for-the-badge&logo=railway&logoColor=white)](https://opspilot-frontend-production.up.railway.app)
[![API Docs](https://img.shields.io/badge/API-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://opspilot-backend-production.up.railway.app/docs)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)]()
[![React](https://img.shields.io/badge/React-Vite-61DAFB?style=for-the-badge&logo=react&logoColor=black)]()

</div>

---

## What is OpsPilot?

OpsPilot is not a chatbot. Give it a *goal* and it autonomously:

1. **Plans** — breaks the goal into ordered steps
2. **Researches** — pulls context from your documents and tools
3. **Executes** — calls APIs, queries GitHub, reads Slack
4. **Verifies** — a Critic agent checks its own output (3 parallel checks)
5. **Reports** — delivers a cited, grounded answer

Sensitive actions (restart service, rollback deployment, create issues) **pause for human approval** before running — via the UI or Slack interactive buttons.

---

## Features

| | Feature | Description |
|--|---------|-------------|
| 🤖 | **Multi-Agent Runs** | Planner → Research → Execution → Critic → Reporting pipeline |
| 💬 | **Streaming Chat** | Tool-augmented copilot with persistent conversation history |
| 📄 | **RAG** | Upload docs; agent cites them with source references |
| 🐙 | **GitHub** | 17 tools — issues, PRs, commits, releases, webhooks |
| 💬 | **Slack** | Bidirectional bot, keyword alerts, event triggers, HITL buttons |
| 👤 | **HITL Approvals** | Sensitive actions require a human green-light |
| 🔌 | **MCP Tool Registry** | Pluggable ecosystem — add any tool with one file |
| 📊 | **Observability** | Prometheus metrics · Grafana dashboard · LangSmith tracing |
| 🏢 | **Multi-Tenant** | Per-user isolation — runs, docs, integrations, tokens |
| 🔑 | **Bring Your Own Key** | Users plug in their own OpenRouter key for unlimited usage |

---

## Architecture

```
Goal
 │
 ▼
┌─────────────────────────────────────────────────────┐
│  Planner Agent — breaks goal into typed steps       │◄─── retry on low confidence
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
              Research Agent (RAG + tools)
                         │
                         ▼
              Security Check
              │              │
         [safe]        [sensitive]
              │              │
              │         HITL pause ──► approve / reject
              │              │
              └──────────────┘
                         │
                         ▼
              Execution Agent (tool calls)
                         │
                         ▼
              Critic Agent (3 parallel checks: correctness · completeness · safety)
                         │
                         ▼
              Reporting Agent ──► Final cited answer
```

---

## Tech Stack

```
Backend     Python · FastAPI (async) · LangGraph · SQLAlchemy · Alembic · Celery
LLM         OpenRouter  (swappable via LLMProvider interface — Ollama supported)
Storage     PostgreSQL (Supabase) · Redis (Upstash) · Qdrant Cloud
Embeddings  BAAI/bge-small-en-v1.5 (dense) + BM25 (sparse) via fastembed
Frontend    React 19 · Vite 5
Deployment  Railway (Docker)
```

---

## Quick Start

### Prerequisites

- Python 3.11+ and Node.js 18+
- PostgreSQL, Redis, Qdrant — or use cloud: Supabase, Upstash, Qdrant Cloud

### Backend

```bash
pip install -r backend/requirements.txt
cp .env.example .env
# fill in DATABASE_URL, REDIS_URL, QDRANT_URL, OPENROUTER_API_KEY, JWT_SECRET …
uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
echo 'VITE_API_URL=http://localhost:8000' > .env.local
npm run dev
```

### Background workers (optional)

```bash
# Celery worker
celery -A backend.workers.celery_app worker --loglevel=info

# Slack bot (Socket Mode)
python -m backend.workers.slack_bot
```

---

## API Reference

**Base URL:** `https://opspilot-backend-production.up.railway.app`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/auth/register` | Register a new user |
| `POST` | `/v1/auth/login` | Login → JWT token |
| `POST` | `/v1/chat/stream` | Streaming chat (SSE) |
| `POST` | `/v1/runs` | Start a multi-agent run |
| `GET` | `/v1/runs` | List all runs |
| `GET` | `/v1/runs/{id}` | Get run detail + tool call log |
| `POST` | `/v1/documents` | Upload document for RAG |
| `POST` | `/v1/documents/ask` | Ask a cited question |
| `GET` | `/v1/mcp/tools` | List all registered tools |
| `GET` | `/v1/approvals` | List pending HITL approvals |
| `POST` | `/v1/approvals/{id}` | Approve or reject an action |
| `GET` | `/metrics` | Prometheus metrics |

Interactive docs available at `/docs`.

---

## Project Structure

```
backend/
├── agents/         # Planner · Research · Execution · Critic · Reporting · Copilot
├── api/routes/     # FastAPI route handlers
├── auth/           # JWT · RBAC · API key gate
├── core/           # Orchestrator · HITL · LangGraph workflow · reflection
├── db/             # SQLAlchemy models · Alembic migrations
├── integrations/   # Encrypted token store · Google OAuth
├── llm/            # LLMProvider interface · OpenRouter · Ollama
├── mcp/            # Tool registry · MCP servers (GitHub, Slack, RAG, …)
├── observability/  # Prometheus metrics · LangSmith tracing
├── rag/            # Chunker · embeddings · Qdrant store · hybrid retriever
├── security/       # RBAC · injection guardrails · secrets redaction
├── tools/          # GitHub · Slack · RAG · monitoring · postgres · web search · …
└── workers/        # Celery tasks · Slack bot · webhook handler · schedules

frontend/src/
├── components/     # Chat · RunList · RunDetail · Settings · Documents · Approvals · …
├── api.js          # Fetch helpers · auth token management
└── App.jsx         # Layout · routing · health polling
```

---

## Environment Variables

See `.env.example` for the full list.

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis URL (`rediss://` for TLS — use Upstash) |
| `QDRANT_URL` + `QDRANT_API_KEY` | Qdrant Cloud endpoint and key |
| `OPENROUTER_API_KEY` | Default LLM key (users can override with their own) |
| `OPENROUTER_MODEL` | Model ID — e.g. `openai/gpt-4o` |
| `JWT_SECRET` | Secret for signing user session tokens |
| `ENCRYPTION_KEY` | Fernet key for storing integration tokens at rest |
| `API_KEY` | Optional Bearer token to gate the entire API |
| `GITHUB_TOKEN` | Default GitHub token (per-user tokens take priority) |
| `GITHUB_WEBHOOK_SECRET` | HMAC secret for webhook signature validation |
| `SLACK_BOT_TOKEN` | Slack bot token (`xoxb-`) |
| `SLACK_APP_TOKEN` | Slack app token for Socket Mode (`xapp-`) |
| `SLACK_SIGNING_SECRET` | For verifying interactive button payloads |
| `GOOGLE_CLIENT_ID/SECRET` | Google OAuth credentials |
| `LANGSMITH_API_KEY` | LangSmith tracing (optional) |

---

<div align="center">
<sub>Private — All rights reserved</sub>
</div>

# OpsPilot — AI Operations Copilot

> An autonomous enterprise AI assistant that takes a goal, plans it, gathers context, reasons across multiple agents, and acts — with human approval where needed.

**Live:** [https://opspilottt.up.railway.app](https://opspilottt.up.railway.app)

---

## What it does

OpsPilot is not a chatbot. Give it a goal; it plans, researches, executes, verifies its own output, and reports back. Sensitive actions (restart service, rollback deployment, create GitHub issues) pause for human approval before running.

**Key capabilities:**

- **Multi-agent runs** — Planner → Research → Execution → Critic → Reporting pipeline with self-reflection
- **Conversational chat** — tool-augmented, streams responses, remembers conversation history
- **RAG** — upload documents; the agent cites them in answers
- **GitHub** — 17 tools: list/create issues, PRs, commits, releases, webhooks
- **Slack** — bidirectional bot, keyword alerts, event triggers, HITL approval buttons
- **Human-in-the-loop (HITL)** — sensitive actions pause the run; approve/reject via UI or Slack
- **MCP tool registry** — pluggable tool ecosystem; add a new tool with one file
- **Observability** — Prometheus metrics, LangSmith tracing, Grafana dashboard
- **Multi-tenant** — every user's data (runs, documents, integrations) is isolated

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Backend | Python + FastAPI (async) |
| Agent orchestration | LangGraph |
| LLM | OpenRouter (swappable via `LLMProvider` interface) |
| Vector DB | Qdrant |
| Database | PostgreSQL (SQLAlchemy + Alembic) |
| Cache + jobs | Redis + Celery |
| Frontend | React + Vite |
| Deployment | Railway |

---

## Getting started (local)

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL, Redis, Qdrant (or use Railway services)

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# fill in .env values
uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
# create frontend/.env.local with:
# VITE_API_URL=http://localhost:8000
npm run dev
```

---

## Environment variables

See `.env.example` for the full list. Key ones:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `QDRANT_URL` | Qdrant connection string |
| `OPENROUTER_API_KEY` | LLM provider key |
| `OPENROUTER_MODEL` | Model to use (e.g. `openai/gpt-4o`) |
| `API_KEY` | Bearer token for API auth |
| `JWT_SECRET` | Secret for user session tokens |
| `ENCRYPTION_KEY` | Fernet key for encrypting stored tokens |
| `GITHUB_TOKEN` | Default GitHub token (per-user tokens override this) |
| `SLACK_BOT_TOKEN` | Slack bot token (`xoxb-`) |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | Must match Google Console redirect URI |

---

## API

Base URL: `https://opspilot-production-85af.up.railway.app`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/auth/register` | Register new user |
| POST | `/v1/auth/login` | Login → JWT token |
| POST | `/v1/chat/stream` | Streaming chat |
| POST | `/v1/runs` | Create a multi-agent run |
| GET | `/v1/runs` | List runs |
| GET | `/v1/runs/{id}` | Get run detail |
| POST | `/v1/documents` | Upload document for RAG |
| GET | `/v1/mcp/tools` | List all available tools |
| GET | `/v1/approvals` | List pending HITL approvals |
| POST | `/v1/approvals/{id}` | Approve or reject |
| GET | `/v1/integrations/{service}` | Check connection status |
| POST | `/v1/integrations/{service}` | Save integration token |
| GET | `/metrics` | Prometheus metrics |

---

## Project structure

```
backend/
  agents/        # Planner, Research, Execution, Critic, Reporting, Copilot
  api/routes/    # FastAPI route handlers
  auth/          # JWT auth + RBAC
  core/          # Orchestrator, HITL, workflow graph, tool router
  db/            # SQLAlchemy models + Alembic migrations
  integrations/  # Token store (encrypted), Google OAuth
  llm/           # LLMProvider interface + OpenRouter impl
  mcp/           # Tool registry + MCP servers
  observability/ # Prometheus metrics + LangSmith tracing
  prompts/       # Dynamic prompt builder
  rag/           # Chunker, embeddings, Qdrant store, retriever, pipeline
  security/      # RBAC, guardrails, secrets redaction
  tools/         # Individual tool implementations
  workers/       # Celery tasks, Slack bot, webhook handler

frontend/src/
  components/    # Chat, RunList, RunDetail, Settings, Documents, Tour, ...
  api.js         # Fetch helpers + auth token management
  App.jsx        # Routing + layout
```

---

## License

Private. All rights reserved.

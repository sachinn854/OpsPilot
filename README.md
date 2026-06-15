# 🔥 AI Operations Copilot

> An autonomous enterprise AI assistant that **takes a goal**, plans it, gathers
> context (tools + RAG + memory), reasons with multiple agents, verifies its own
> output, and acts — with human approval for sensitive actions.

It is **not** a chatbot that just replies with text. It investigates incidents,
queries systems, retrieves organizational knowledge, and runs operational
workflows autonomously.

---

## 📚 Project documents

| File | What it covers |
|------|----------------|
| **`info.md`** | Original project spec / vision |
| **`ARCHITECTURE.md`** | The full system design — *what* gets built |
| **`ROADMAP.md`** | Phase-by-phase build plan — *what to do next* |
| **`CLAUDE.md`** | Working rules for the AI assistant (auto-loaded) |

👉 **Start here:** read `ARCHITECTURE.md` for the design, then follow `ROADMAP.md`.

---

## 🧱 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python + FastAPI |
| Agent orchestration | LangGraph |
| LLM | Groq |
| Vector DB | Qdrant |
| Main DB | PostgreSQL |
| Cache + async jobs | Redis + Celery |
| Frontend | React |
| Observability | LangSmith + Prometheus + Grafana |

---

## 🚀 Local setup

### 1. Prerequisites
- Python 3.11+
- Docker Desktop (for Postgres, Redis, Qdrant)
- Node.js 18+ (for the React frontend, added later)

### 2. Configure environment
```bash
# copy the template and fill in your keys
copy .env.example .env          # Windows
# cp .env.example .env          # Mac/Linux
```
Then open `.env` and set **`GROQ_API_KEY`** (get a free key at https://console.groq.com).

### 3. Start the services
```bash
docker-compose up -d
```
This starts PostgreSQL (5432), Redis (6379), and Qdrant (6333).

### 4. Install Python dependencies
```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # Mac/Linux
pip install -r requirements.txt
```

### 5. Run the API
```bash
uvicorn backend.main:app --reload
```
- Health check → http://localhost:8000/health
- API docs (Swagger) → http://localhost:8000/docs

---

## 🗺️ Build status

Currently at **Phase 0 — Project setup & skeleton**.
See `ROADMAP.md` for the full phase plan and progress tracker.

---

## 📂 Structure (high level)

```
backend/    # FastAPI app, agents, core, tools, rag, db
frontend/   # React dashboard (added in later phases)
docs/       # architecture, runbooks
tests/      # tests
```

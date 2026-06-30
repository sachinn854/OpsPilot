# CLAUDE.md — AI Operations Copilot

> This file is read automatically at the start of every session. It tells Claude
> what this project is, how to build it, and how to behave. Keep it short and current.

---

## 🎯 What this project is

**AI Operations Copilot** — an autonomous enterprise AI assistant. It does NOT just
answer questions; it takes a *goal*, plans it, gathers context (tools + RAG + memory),
reasons with multiple agents, verifies its own output, and acts (with human approval).

- Full design → see **`ARCHITECTURE.md`**
- Build plan / what to do next → see **`ROADMAP.md`**
- Original spec → see **`info.md`**

**Always read `ROADMAP.md` to know the current phase and what to build next.**

---

## 🧱 Tech Stack (locked — do not change without asking)

| Layer | Choice |
|-------|--------|
| Backend | **Python + FastAPI** |
| Agent orchestration | **LangGraph** |
| LLM provider | **Groq** (via an `LLMProvider` interface — keep it swappable) |
| Vector DB | **Qdrant** |
| Main DB | **PostgreSQL** (SQLAlchemy + Alembic) |
| Cache + async jobs | **Redis + Celery** |
| Tools | Hybrid: in-process `Tool` interface now → **MCP** servers in Phase 5 |
| Observability | LangSmith + Prometheus + Grafana |
| Frontend | **React** (professional dashboard) |

---

## 🛠️ How we build

- Follow **`ROADMAP.md` phase by phase**. Do not skip ahead. Don't start a phase
  until the previous phase's "Done when" is satisfied.
- **Current status:** Phases 0–6 ✅ done. Phase 7 (Production Readiness / Deployment) = next.
  (See the Build Log below for details.)
- Each phase must be **demoable** before moving on.
- Update the Progress Tracker in `ROADMAP.md` **and the Build Log below** as work lands.

### Code conventions
- **Python:** async/await everywhere (FastAPI is async). Type hints required.
- **Validation:** use **Pydantic** models for all agent I/O and API schemas.
- **Tools:** every tool implements the standard `Tool` interface (`ARCHITECTURE.md` §5.9).
- **LLM calls:** always go through the `LLMProvider` abstraction, never call Groq SDK directly in agents.
- **Secrets:** only from `.env` / environment. Never hardcode keys. Never log secrets.
- **DB:** every table has `org_id` (multi-tenant). Use migrations (Alembic), not manual SQL.
- Keep functions small and single-purpose; match the architecture's separation of concerns.

### Folder structure
Follow the layout in `ARCHITECTURE.md` §9 — each concept maps to one package
(`core/`, `agents/`, `memory/`, `rag/`, `tools/`, `security/`, `db/`, etc.).

---

## 💬 How to talk to me (the user)

- Reply in **Hinglish** (Hindi + English mix), the way the user writes.
- Keep explanations **simple and short**; use examples, tables, and diagrams.
- Before writing big things, **briefly confirm the plan**, then build.
- When unsure about a product decision, **ask** rather than assume.

---

## ⚙️ Environment notes

- OS: **Windows** — primary shell is **PowerShell** (Bash tool also available).
- Services run via **Docker** (`docker-compose`): Postgres, Redis, Qdrant.
- Python project lives under `backend/`; React app under `frontend/`.

---

## ✅ Definition of done (every change)

1. Code follows the conventions above.
2. It maps to the right phase/folder in the architecture.
3. There's at least a happy-path test or a clear way to demo it.
4. No secrets committed; `.env.example` updated if new env vars are added.
5. **Update the Build Log below** (and `ROADMAP.md`'s tracker) so progress is tracked.

> ⚠️ **Maintenance rule:** This file is the living source of truth. After **every
> meaningful change** (new feature, new file, config/env change, phase done),
> append/adjust the Build Log so anyone reading CLAUDE.md knows exactly what exists.

---

## 📋 Build Log (what actually exists)

> High-level changelog. Newest phase first. Code is the detail; this is the map.

### Phase 0 — Setup & skeleton ✅
- FastAPI app (`backend/main.py`) + `/health` endpoint.
- `config.py` (Pydantic settings from `.env`), `.env.example` template.
- `docker-compose.yml`: Postgres (5433), Redis (6380), Qdrant (6335).
- `db/session.py` (async SQLAlchemy), `db/redis.py`.

### Phase 1 — Basic Copilot (single agent) ✅
- `llm/base.py` (`LLMProvider` interface) + `llm/groq_provider.py` (Groq impl,
  with tool-call retry for Groq's `tool_use_failed` 400s).
- `agents/base.py` + `agents/copilot.py` — single agent that chats + calls tools.
- `tools/base.py` (`Tool` interface) + `tools/github.py` (issues/commits).
- `core/tool_router.py` — register + dispatch tools.
- `api/routes/chat.py` — `POST /v1/chat`.
- `db/models.py` — `conversations`, `messages` (all with `org_id`).

### Phase 2 — Advanced RAG ✅ (ingest + hybrid retrieve + cited answers)
- **Embeddings (local, free):** `rag/embeddings.py` via **fastembed** —
  dense `BAAI/bge-small-en-v1.5` (384-dim) + sparse `Qdrant/bm25`.
- `rag/chunker.py` — overlapping chunks on natural boundaries (size 800 / overlap 150).
- `rag/extract.py` — text from `.txt/.md/.pdf` (pypdf).
- `rag/store.py` — Qdrant: named vectors (`dense` + `bm25`), org-filtered.
  `hybrid_search()` = dense + BM25 prefetch fused with **RRF** (`FusionQuery`).
- `rag/ingest.py` — load → chunk → embed (dense+sparse) → upsert + persist rows.
- `rag/retriever.py` — embed query → hybrid/dense search → typed top-k chunks.
- `rag/pipeline.py` — grounded answer: answer ONLY from numbered context, cite `[n]`.
- `tools/rag.py` — `search_documents` tool (wired into the Copilot agent).
- `api/routes/documents.py` — `POST /v1/documents` (upload), `POST /v1/documents/ask`
  (cited answer), `GET /v1/documents` (list).
- `db/models.py` — added `documents`, `document_chunks` (with `org_id`, `point_id`).
- **Toggles:** `RAG_HYBRID=true` (on), `RAG_RERANK=false` (cross-encoder, future).
- Verified end-to-end: upload → `/ask` cited answer + agent auto-calls the tool.

### Phase 3 — Multi-Agent System ✅ (Planner→Research→Execution→Critic→Reporting)
- `agents/structured.py` — `complete_structured()`: forces typed JSON output from
  the LLM, validates against a Pydantic schema, retries once with the error fed back.
- `agents/planner.py` — goal → typed `Plan` (ordered `PlanStep`s tagged
  research/execution); accepts Critic `feedback` to revise on retry.
- `agents/research.py` — RAG retrieve → grounded `ResearchNotes` (notes + sources).
- `agents/execution.py` — tool-calling loop via Tool Router → `ExecutionResult`
  (output + structured `ToolCallLog` of every call).
- `agents/critic.py` — strict verifier → `Verdict` (passed, confidence 0-1, feedback).
- `agents/reporting.py` — composes the final human-facing answer + evidence.
- `core/workflow/state.py` — `RunState` (TypedDict) flowing through the graph.
- `core/workflow/graph.py` — LangGraph wiring: planner→research→execution→critic,
  conditional edge loops back to planner on low confidence, else → reporting → END.
- `core/reflection.py` — `should_retry()` gate (confidence threshold + retry budget).
- `core/orchestrator.py` — owns a run: creates `Run` row, drives the graph,
  persists plan/report/confidence/attempts + the tool-call audit trail.
- `core/tool_router.py` — added `build_default_router()` so chat + runs share tools.
- `api/routes/runs.py` — `POST /v1/runs` (goal → run), `GET /v1/runs` (list),
  `GET /v1/runs/{id}` (detail).
- `db/models.py` — added `runs`, `tool_calls` (`ToolCallRecord`) tables (org_id).
- **Config:** `CRITIC_CONFIDENCE_THRESHOLD=0.7`, `RUN_MAX_RETRIES=2`.
- Verified end-to-end: happy path (conf 1.0, attempts 1, cited from `hr.txt`) and
  the retry loop (unanswerable goal → conf 0.0, attempts 3 → honest "can't determine").

### Phase 4 — HITL + Security ✅
**4A — Human-in-the-loop (done & tested):**
- `agents/security_agent.py` — classifies a goal/plan as sensitive vs safe
  (LLM judgment + deterministic backstop against known sensitive tool names).
- `tools/ops.py` — mock SENSITIVE tools `rollback_deployment`, `restart_service`
  (simulated, no real infra) so HITL is demoable; `Tool.sensitive` flag added.
- `core/workflow/graph.py` — added `security` + `hitl` nodes. Sensitive → `hitl`
  calls LangGraph `interrupt()` → run PAUSES. Approve → execution; reject → reporting.
  Compiled with a `MemorySaver` checkpointer (in-process; Postgres saver = future).
- `core/hitl.py` — approval persistence (create pending / list / record decision).
- `core/orchestrator.py` — detects pause (`snapshot.next` + `tasks[].interrupts`),
  records a pending `Approval` + sets run `awaiting_approval`; `resume_run()` continues
  via `Command(resume=...)`. Shared `_finalize`/`_fail`/`_pause` helpers.
- `core/reflection.py` — guard: once a sensitive action is approved+executed, never
  retry (avoids re-running the side-effecting action on a Critic loop).
- `db/models.py` — added `approvals` table (run_id, action, payload, status, decided_by).
- `api/deps.py` — process-wide Orchestrator singleton (keeps the paused-run checkpoint
  alive between the run request and the approval request).
- `api/routes/approvals.py` — `GET /v1/approvals` (pending), `POST /v1/approvals/{id}`
  (approve/reject → resume/abort).
- Verified: sensitive→pause→**approve**→executes (tool calls run); sensitive→**reject**
  →aborts (0 tool calls); safe goal → no pause (no regression).

**4B — Security hardening (done & tested):**
- `security/rbac.py` — `Role` enum (viewer=1 < operator=2 < admin=3), `get_role()`
  reads `X-User-Role` header (default viewer), `require_role(min)` FastAPI dep → 403
  if caller's role is too low.
- `security/guardrails.py` — `check_injection(text)` → `GuardResult(safe, reason)`;
  11 regex patterns for known injection techniques (ignore_instructions, act_as,
  jailbreak, DAN mode, role_spoof, etc.).
- `security/secrets.py` — `redact(text)` replaces API keys / tokens / passwords with
  `[REDACTED:<type>]` before text reaches the LLM or logs. Wired in `execution.py`
  (tool results sanitized before they go back to the LLM).
- **Rate limiting** via `slowapi==0.1.10` (per-IP, in-memory): chat 30/min,
  runs 10/min, approvals 20/min. Limits are env-overridable
  (`RATE_LIMIT_CHAT/RUNS/APPROVALS`). Limiter lives in `api/deps.py`; wired to
  `app.state.limiter` + `RateLimitExceeded` handler in `main.py`.
- **Route enforcement:** `POST /v1/runs` → operator+ RBAC + guardrail + rate limit;
  `POST /v1/approvals/{id}` → operator+ RBAC + rate limit;
  `POST /v1/chat` → guardrail + rate limit; all GETs → rate limit only (viewer OK).
- `config.py` — added `RATE_LIMIT_*` settings; `.env.example` updated.
- Verified: `viewer` → 403 on POST /runs; injection → 400; secrets redacted in
  tool-result stream; 429 after rate limit exceeded.

### Phase 5 — MCP Ecosystem ✅ (pluggable tool registry + discovery API)
- `mcp/types.py` — `MCPToolSpec` Pydantic model (name, description, parameters,
  server, sensitive) — the universal tool descriptor.
- `mcp/adapter.py` — `tool_to_spec()` bridge + `MCPServer` abstract class. Every
  server is a named group of tools (`name = "github"`, `tools() → list[Tool]`).
- `mcp/registry.py` — `ToolRegistry`: holds all MCPServers, filters by
  `TOOLS_ENABLED` config, exposes `list_specs()`, `build_router()`, `get_tool()`.
- **6 MCP servers** in `mcp/servers/`:
  `GitHubServer`, `OpsServer`, `RagServer`, `SlackServer`, `SearchServer`,
  `MonitoringServer` — each wraps its tools under a domain name.
- **5 new tools** (mocked — wire real APIs when credentials available):
  - `tools/slack.py` — `PostMessageTool` (Slack message posting)
  - `tools/web_search.py` — `WebSearchTool` (internet search)
  - `tools/filesystem.py` — `ReadFileTool`, `ListFilesTool` (workspace files)
  - `tools/monitoring.py` — `GetServiceHealthTool`, `GetMetricsTool` (metrics)
  - `tools/postgres.py` — `ExecuteSQLTool` (read-only SQL, SELECT-only guard)
- `api/routes/mcp.py` — `GET /v1/mcp/tools` (list 12 tools with specs),
  `GET /v1/mcp/servers` (active servers + count), `POST /v1/mcp/tools/{name}`
  (direct tool call, operator+ RBAC). Adding a new tool = add a server file + config.
- `api/deps.py` — `get_registry()` singleton; `get_orchestrator()` now uses
  `registry.build_router()` instead of hardcoded tool list; chat also uses registry.
- `config.py` — `TOOLS_ENABLED=github,rag,ops,slack,search,monitoring`
  (comma-separated, or "all"); `.env.example` updated.
- **Demo verified:** 12 tools discovered; slack tool called directly via API;
  viewer → 403; unknown tool → 404; adding a tool = one file + config line.

### Phase 6 — Observability + Reflection + Frontend ✅
**Prometheus metrics (`observability/metrics.py` — already committed as `c4210a4`):**
- 7 metrics: `RUNS_TOTAL` (counter, labelled by status), `RUN_DURATION` (histogram,
  custom buckets), `TOOL_CALLS_TOTAL` (counter, tool_name+ok), `ACTIVE_APPROVALS`
  (gauge), `LLM_REQUESTS_TOTAL`, `LLM_TOKENS_TOTAL` (prompt/completion), `CRITIC_RETRIES_TOTAL`.
- `main.py` mounts `make_asgi_app()` at `/metrics` for Prometheus scraping.
- `requirements.txt` — added `prometheus-client==0.21.1`.

**Metric instrumentation (commit `fea7907`):**
- `llm/groq_provider.py` — increments `LLM_REQUESTS_TOTAL` + `LLM_TOKENS_TOTAL` per call.
- `core/orchestrator.py` — `RUN_DURATION`, `RUNS_TOTAL`, `TOOL_CALLS_TOTAL`, `ACTIVE_APPROVALS.inc()`.
- `core/hitl.py` — `ACTIVE_APPROVALS.dec()` after approve/reject.
- `core/reflection.py` — `CRITIC_RETRIES_TOTAL` on each retry.

**LangSmith tracing (commit `3a131bf`):**
- `observability/tracing.py` — `init_tracing()` activates `LANGCHAIN_TRACING_V2` when
  `LANGSMITH_API_KEY` is set. Called in `main.py` lifespan startup.
- `config.py` + `.env.example` — `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` settings added.

**Celery async workers (commits `54b278b`, `69557ad`):**
- `workers/celery_app.py` — Celery instance (Redis broker+backend, JSON serializer, 600s hard limit).
- `workers/tasks.py` — `morning_github_report` (GitHub→Slack digest, Mon-Fri 08:00 UTC),
  `run_health_check` (pipeline smoke-test every 30 min); both use `asyncio.run()`.
- `workers/schedules.py` — Celery Beat schedule config.

**Grafana + Prometheus infra (commit `191d254`):**
- `infrastructure/monitoring/prometheus.yml` — scrape config for `host.docker.internal:8000/metrics`.
- `infrastructure/monitoring/grafana/` — provisioned datasource + 8-panel dashboard
  (runs, p95 duration, pending approvals gauge, tokens, time-series charts).
- `docker-compose.yml` — `prometheus` (9090) and `grafana` (3001) services with
  `extra_hosts: host.docker.internal=host-gateway`.

**Multi-check Critic (commit `d4f27d5`):**
- `agents/critic.py` rewritten with 3 concurrent LLM checks: correctness, completeness, safety.
- `asyncio.gather()` fans all three out in parallel; mean confidence; backward-compatible `Verdict`.

**React dashboard frontend (commit `e658522`):**
- Vite 5 + React app in `frontend/`; dev proxy `/v1` → `localhost:8000`.
- `src/api.js` — fetch helpers: fetchRuns, fetchRun, createRun, fetchApprovals, decide, fetchMcpTools.
- Pages: RunList, RunDetail (plan + tool-call timeline + report), NewRun form,
  ApprovalPanel (approve/reject buttons), ToolsPanel (MCP tools grouped by server).
- Dark-mode design system in `App.css` (sidebar, cards, badges, buttons, form fields).

### Audit + Hardening (56/96 findings fixed across 6 commits)

**LLM provider (commits `5677d32`):**
- `llm/openrouter_provider.py` — NEW: OpenRouter via `openai` package (base_url swap);
  3-attempt retry only on tool-schema validation errors; streams SSE; instruments metrics.
- Groq replaced everywhere; model name read from `OPENROUTER_MODEL` in `.env` only.
- `config.py` — `OPENROUTER_API_KEY/MODEL`, `API_KEY` (Bearer gate), `CRITIC_CONFIDENCE_THRESHOLD`
  field_validator (0.0–1.0), `LOG_LEVEL` applied via `logging.basicConfig` in `main.py`.

**Security hardening (commit `86b7d64`):**
- `security/rbac.py` — `_validate_api_key` dep: `Authorization: Bearer <API_KEY>` required when
  `API_KEY` is set; role header only trusted after key verified.
- `security/secrets.py` — OpenRouter `sk-or-v1-*` pattern added to `redact()`.
- `tools/github.py` — `_validate_repo()` regex blocks SSRF via model-generated repo strings.
- `tools/postgres.py` — blocks stacked queries (semicolons) + all write keywords.
- `api/routes/documents.py` — `require_role`, rate limit, 20 MB cap, filename sanitize, suffix whitelist.
- `api/routes/approvals.py` — `decided_by` server-derived; `SELECT FOR UPDATE` prevents TOCTOU.
- `api/routes/runs.py` — 2000-char goal limit; GET pagination (limit param, default 50).

**Bug fixes (commit `81c73d2`):**
- `core/orchestrator.py` — 5-min `asyncio.wait_for` timeout; `asyncio.Lock` for MemorySaver;
  `_fail()` returns `RunResult` (no re-raise); sources deduped across retry loops.
- `core/hitl.py` — `ACTIVE_APPROVALS.dec()` guarded against going negative.
- `agents/copilot.py` — tool results capped at 8000 chars in `run()` and `run_stream()`.
- `agents/reporting.py` — `redact()` applied to execution_output + research_notes before LLM.
- `api/routes/chat.py` — lazy `@lru_cache` singleton; history capped at 40 messages;
  uses `build_default_router()` (same tool set as orchestrator).

**RAG hardening (commit `8292e82`):**
- `rag/store.py` — `on_disk=True` for dense + sparse vectors (prevents OOM on large KB).
- `rag/ingest.py` — Postgres commit FIRST, then Qdrant; compensating delete if Qdrant fails.
- `rag/retriever.py` — hybrid search try/except → dense-only fallback.
- `rag/extract.py` — `PdfReadError` caught + clear error for empty-text PDFs.
- `tools/rag.py` — chunk text capped at 2000 chars per chunk.
- `tools/web_search.py` — returns `ok=False` error instead of fake simulated results.

**MCP + observability (commit `6316f58`):**
- `mcp/registry.py` — `build_router()` cached on instance; no duplicate client instances.
- `mcp/servers/github_server.py` — `GitHubPRsTool` added (was missing from MCP server).
- `observability/metrics.py` — `ACTIVE_APPROVALS.set(0)` at startup for clean Prometheus scrape.

**Frontend (commit `d1597a9`):**
- `components/Chat.jsx` — new file; `AbortController` per request + Stop button; 4000-char limit.
- `components/Documents.jsx` — new file; citation score shown as `%` not raw float.
- `src/api.js` — `apiFetch()` wrapper with 30s `AbortSignal.timeout`; uniform error handling.
- `components/RunDetail.jsx` — exponential-backoff polling (2s→30s) for in-progress runs.
- `components/ApprovalPanel.jsx` — `window.confirm()` before approve/reject.
- `App.jsx` — `/health` polled every 30s; badge turns red when backend unreachable.
- `App.css` — `.online-badge.offline` red style.

### GitHub Integration — G1, G2, G3, G4 ✅

**G1 — 17 GitHub tools (commit `874f078`):**
- `tools/github.py` rewritten: 11 read tools + 4 write tools (sensitive=True) + 2 original list tools.
- `_get_org_token(org_id)` fetches per-user token from DB; falls back to `.env GITHUB_TOKEN`.
- `mcp/servers/github_server.py` updated to register all 17 tools.
- `core/tool_router.py` `build_default_router()` registers all 17 GitHub tools.

**G2 — Per-user token management (commit `ab18ad6`):**
- `integrations/encrypt.py` — Fernet AES-128 encrypt/decrypt for tokens at rest.
- `integrations/store.py` — `save_token`, `get_token`, `delete_token`, `list_connected`.
- `db/models.py` — `IntegrationToken` table (org_id + service unique constraint).
- `api/routes/integrations.py` — CRUD: GET/POST/DELETE `/v1/integrations/{service}` + live verify.
- `frontend/src/components/Settings.jsx` — UI: 4 service cards (GitHub, Slack, Jira, Linear) with connect/disconnect/verify buttons.
- `config.py` — `ENCRYPTION_KEY` setting; `.env.example` updated.

**G3 — Write tools + HITL security-agent fix (commit `4e1dcd1`):**
- `agents/security_agent.py` — fixed verb extraction: skips service-name prefixes
  (`_SKIP_PREFIXES`) so `github_create_issue` → verb `"create"` not `"github"`.
- Write tools already wired with `sensitive=True`; HITL graph already in place — no graph changes needed.

**G4 — GitHub Webhooks:**
- `db/models.py` — `WebhookEvent` table (source, event_type, action, delivery_id, payload, processed).
- `api/routes/webhooks.py` — `POST /v1/webhooks/github`: HMAC-SHA256 signature verify →
  persist raw payload → queue Celery task → return fast 200.
- `workers/webhook_handler.py` — `process_webhook_event` Celery task; handlers for
  push, pull_request, issues, release; marks row processed=True.
- `config.py` — `GITHUB_WEBHOOK_SECRET` setting; `.env.example` updated.
- `frontend/src/components/Settings.jsx` — webhook setup instructions card.

### Advanced Slack Features ✅ (4 features across 4 commits)

**S1 — Keyword Alerts (commit `2101d35`):**
- `db/models.py` — `SlackKeywordAlert` table (org_id, keyword, channels, notify_via, is_active).
- `api/routes/slack_features.py` — CRUD: GET/POST/PATCH/DELETE `/v1/slack/alerts`.
- `workers/tasks.py` — `scan_keyword_alerts` Celery task: scans last 20 min of messages per active alert;
  fires email (SMTP) and/or Slack DM when keyword matched; dynamically discovers bot's channels.
- `workers/schedules.py` — `slack-keyword-scan` runs every 15 minutes.

**S2 — Bidirectional Slack Bot / Socket Mode (commit `96a108c`):**
- `workers/slack_bot.py` — `AsyncApp` with Socket Mode; handles `message.im` (DMs) and
  `app_mention` events; runs each message through `CopilotAgent` and replies in-thread.
  Also processes active `SlackEventTrigger` rows for any channel message.
- `config.py` — `SLACK_APP_TOKEN` (xapp-...) setting.
- Start command: `python -m backend.workers.slack_bot`.

**S3 — HITL from Slack interactive buttons (commit `141d459`):**
- `api/routes/slack_interactive.py` — `POST /v1/slack/interactive`; verifies Slack signing secret;
  parses block_actions payload; calls `orchestrator.resume_run()` on approve/reject; updates
  original Slack message via `response_url`.
- `core/hitl.py` — `create_pending_approval()` now fires `_notify_slack_hitl()` as a background task:
  finds an #approvals / #ops / #general channel and posts an interactive message with Approve/Reject buttons.
- `config.py` — `SLACK_SIGNING_SECRET` setting.
- Setup: Interactivity & Shortcuts → Request URL: `https://<domain>/v1/slack/interactive`.

**S4 — Event Triggers + Frontend (commit `062a79c`):**
- `api/routes/slack_features.py` — CRUD for `SlackEventTrigger`: GET/POST/PATCH/DELETE `/v1/slack/triggers`.
- `workers/slack_bot.py` — `_check_triggers()` matches incoming messages against active triggers;
  dispatches to `create_github_issue`, `post_to_channel`, or `run_copilot` actions.
- `frontend/src/components/SlackFeatures.jsx` — new page (3 tabs: Keyword Alerts, Event Triggers, Bot Setup Guide).
- `frontend/src/App.jsx` — `#` Slack nav item in System section routes to `<SlackFeatures />`.
- `requirements.txt` — `slack-bolt>=1.21.0` added.

**Also in this session (earlier commits):**
- `prompts/` — modular per-turn dynamic prompt system (base + per-service sections injected by keyword scan).
- `agents/copilot.py` — rewired to use `build_prompt_for_turn` per turn.
- `tools/workflows.py` + `mcp/servers/workflow_server.py` — 4 cross-service compound tools
  (standup, stale PR notifier, incident broadcast, PR stakeholder DMs).
- `workers/tasks.py` — `slack_channel_digest` Celery task (LLM summary of all channels, twice daily).
- `workers/email_utils.py` — SMTP email sender for digest delivery.
- `db/models.py` — `User.digest_email_enabled`, `User.digest_email_override` columns.
- `api/routes/auth.py` — `GET /v1/auth/me` returns digest prefs; `PATCH /v1/auth/digest-prefs`.
- `frontend/src/components/Settings.jsx` — TokenGuide expandable setup guides + email digest toggle.
- `auth/utils.py` — replaced passlib with direct bcrypt (SHA-256 pre-hash) to fix version incompatibility.

---

*When in doubt: read `ARCHITECTURE.md` for the "what", `ROADMAP.md` for the "next",
and this Build Log for "what already exists".*

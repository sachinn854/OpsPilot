# Security & Quality Audit Report — AI Operations Copilot

**Date:** 2026-06-24  
**Audited by:** Automated multi-agent review (5 parallel auditors)  
**Total findings:** 96 (after dedup from 109 raw)  
**Fixed:** All 6 CRITICAL + 30 HIGH + 14 MEDIUM + 6 LOW ✅ (56/96 total)

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 6 |
| 🟠 HIGH | 34 |
| 🟡 MEDIUM | 35 |
| 🟢 LOW | 21 |

---

## 🔴 CRITICAL

---

### 1. `backend/security/rbac.py:21-32` — Role spoofable via unauthenticated HTTP header

The entire RBAC system trusts the value of the `X-User-Role` HTTP header set by the caller. Any unauthenticated client can send `X-User-Role: admin` and gain full admin privileges. There is no token, session, or JWT verification — the header is accepted at face value.

**Fix:** Remove header-based role resolution. Implement proper authentication (JWT Bearer tokens, API keys stored in DB) and derive the role from a verified identity. Require a signed, server-issued token that carries the role claim and verify the signature in `get_role()`.

---

### 2. `backend/core/orchestrator.py:249-257` — `_fail()` commits error state then re-raises, breaking callers

`_fail()` calls `await session.commit()` to persist the failed run, then calls `raise exc`. Callers use `return await self._fail(...)` expecting a `RunResult` back. The re-raise means neither caller ever returns — the exception bubbles to the API route. The route only catches `RuntimeError` and `ValueError`, so any other exception type results in a 500 with a full traceback. The declared return type `-> RunResult` is a lie.

**Fix:** Remove `raise exc` from `_fail()` and return a proper `RunResult(status='failed', ...)`. This gives callers a consistent return type and lets the route decide the HTTP status code.

---

### 3. `backend/core/orchestrator.py:115-141` — Approval check and resume are not atomic (TOCTOU double-resume)

In `approvals.py` the route checks `approval.status != 'pending'`, then calls `hitl.record_decision()` and `orchestrator.resume_run()` in three separate unlocked steps. Under concurrent requests (two operators clicking Approve simultaneously), both pass the status check before either writes — `resume_run()` is called twice, potentially double-executing sensitive tool calls or corrupting run state.

**Fix:** Use `SELECT ... FOR UPDATE` (pessimistic lock) on the Approval row before checking status. Alternatively use an optimistic `UPDATE approvals SET status=? WHERE id=? AND status='pending'` and check `rowcount == 1` before proceeding.

---

### 4. `backend/config.py:31` — Hardcoded weak Postgres credentials in default `DATABASE_URL`

The `Settings` class has a hardcoded default: `postgresql+asyncpg://copilot:copilot_pass@localhost:5432/copilot`. If `.env` is absent or incomplete, the application silently connects with these known-weak credentials, which are also publicly visible in source control. Same password is hardcoded in `docker-compose.yml`.

**Fix:** Remove the default value entirely. Add a startup validator that raises an error if `DATABASE_URL` is empty. Rotate the docker-compose password to something randomly generated and store it only in a secrets manager or `.env` that is never committed.

---

### 5. `backend/rag/ingest.py:38-84` — Qdrant upsert before Postgres commit with no rollback on failure

Flow: flush doc row → build chunks → upsert to Qdrant → commit Postgres. If Qdrant succeeds but `session.commit()` fails, vectors are permanently orphaned in Qdrant with no matching Postgres rows. Searches will return payloads whose `document_id`/`point_id` no longer exist in the DB, causing citation errors. Reverse also true: if Qdrant fails, no cleanup is attempted.

**Fix:** Commit Postgres first (to confirm `doc.id` and `point_id`s), then upsert to Qdrant. Wrap the Qdrant upsert in a `try/except` that issues a compensating `client.delete(collection, ids=[...])` if Qdrant fails after a successful DB commit.

---

### 6. `backend/core/orchestrator.py:96-101` — `MemorySaver` shared across concurrent runs — thread collision and lost state on restart

The `Orchestrator` is a singleton via `@lru_cache`. Its `self.graph` is compiled with a single `MemorySaver()` shared by all runs. `MemorySaver` is not thread-safe for concurrent writes. On server restart, all paused run checkpoints are lost — any pending approvals in the DB can never be resumed.

**Fix:** Use a per-request graph instance (call `build_graph()` per run), or upgrade to a Postgres-backed checkpointer (`AsyncPostgresSaver`) for production. Document clearly that `MemorySaver` means paused runs are lost on restart.

---

## 🟠 HIGH

---

### 7. `backend/api/routes/approvals.py:36-38` — `decided_by` is a free-form caller-supplied string

`DecisionRequest` accepts `decided_by: str = "operator"` from the request body. Any caller can claim any identity (`decided_by: "cto"`) without verification. This audit field is written to the DB and is therefore misleading and untrustworthy.

**Fix:** Derive `decided_by` from the authenticated identity (JWT `sub` claim or verified API-key principal), not from the request body. Remove it from `DecisionRequest`.

---

### 8. `backend/api/routes/documents.py:46-74` — Document upload has no authentication or rate limiting

`POST /v1/documents` accepts file uploads with no `require_role` dependency and no rate limiter. Any anonymous caller can flood the service with ingestion requests, exhausting CPU (embedding), Qdrant disk, and Postgres storage.

**Fix:** Add `require_role(Role.operator)` as a dependency and apply `@limiter.limit(...)`. Mirror the pattern used on `POST /v1/runs`.

---

### 9. `backend/api/routes/documents.py:77-86` — `/ask` endpoint has no auth, no rate limit, no injection guard

The `/ask` endpoint triggers an LLM call with no authentication, no rate limiting, and no `check_injection()` guard. An anonymous attacker can flood LLM API credits or inject instructions into the RAG pipeline's LLM prompt.

**Fix:** Add `require_role(Role.viewer)`, `@limiter.limit(settings.RATE_LIMIT_CHAT)`, and `check_injection(req.question)` before the LLM call.

---

### 10. `backend/api/routes/documents.py:51-56` — No file size limit, MIME validation, or filename sanitisation

`raw = await file.read()` with no size cap — a 1 GB upload will be held in RAM. Filename stored directly from `file.filename` without sanitisation; only extension checked via string suffix, not actual content/MIME type.

**Fix:** Enforce max upload size (e.g., 20 MB) before reading. Validate MIME type against `Content-Type`. Sanitise filename with `pathlib.Path(file.filename).name` to strip path traversal components.

---

### 11. `backend/tools/github.py:54` — User-controlled `repo` interpolated directly into URL (SSRF)

The `repo` parameter from the LLM is placed directly into the URL: `f"{GITHUB_API}/repos/{repo}/issues"`. A value like `../../user` could redirect to unintended GitHub API endpoints. Same pattern exists in `GitHubPRsTool` and `GitHubCommitsTool`.

**Fix:** Validate that `repo` matches `r'^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$'` before interpolating into the URL.

---

### 12. `backend/tools/postgres.py:29-43` — SQL injection via bypassable SELECT-only guard

The SELECT-only guard is `q_lower.startswith("select")`, trivially bypassed with `SELECT 1; DROP TABLE users--`. The model-generated query is executed with no parameterisation.

**Fix:** Use `sqlparse` to parse the statement and assert there is exactly one statement of type `SELECT` before executing. Or use `psycopg2` read-only transaction mode (`set_session(readonly=True)`).

---

### 13. `backend/api/routes/chat.py:30` — Module-level `_copilot` created at import time

`_copilot = CopilotAgent(llm=OpenRouterProvider(), ...)` runs at module import. If `OPENROUTER_API_KEY` is missing, the app crashes on startup before serving `/health`.

**Fix:** Lazy-initialise `_copilot` inside a `@lru_cache` function or use FastAPI's lifespan event so startup errors are caught and reported cleanly.

---

### 14. `backend/agents/copilot.py` — Tool call loop has no max iteration limit

The `while True` tool loop in `run()` and `run_stream()` has no hard cap on iterations. A misbehaving model that keeps emitting tool calls (or a buggy tool that always returns an error the model retries) will loop forever.

**Fix:** Add `max_tool_rounds = 10` and break with an error message if exceeded.

---

### 15. `frontend/src/components/Chat.jsx` — SSE connection never aborted on component unmount

The `fetch` + `ReadableStream` SSE connection is opened but no `AbortController` is created. When the user navigates away mid-stream, the connection stays alive, the `setMessages` calls fire on an unmounted component, and React logs state update warnings. Memory leak accumulates across navigations.

**Fix:** Create an `AbortController` in the effect, pass `signal` to `fetch`, and call `controller.abort()` in the effect cleanup function.

---

### 16. `frontend/src/api.js` — No request timeout or global error handling

All `fetch` calls have no timeout. A hung backend will keep the UI in a loading state indefinitely. Network errors are not caught uniformly — some callers get an unhandled promise rejection.

**Fix:** Wrap all `fetch` calls with an `AbortSignal.timeout(30_000)`. Add a shared `apiFetch` wrapper that catches and normalises errors.

---

### 17. `backend/db/models.py` — Missing indexes on hot query columns

`Message.conversation_id`, `Run.org_id`, `ToolCallRecord.run_id`, `Approval.run_id` are queried on every request but have no explicit index. At scale (>10K rows) these become full-table scans.

**Fix:** Add `index=True` to these foreign key columns in the SQLAlchemy model definitions, or add explicit `Index(...)` objects.

---

### 18. `backend/db/models.py` — No CASCADE deletes defined

Deleting a `Conversation` leaves orphaned `Message` rows. Deleting a `Run` leaves orphaned `ToolCallRecord` and `Approval` rows. Deleting a `Document` leaves orphaned `DocumentChunk` rows.

**Fix:** Add `cascade="all, delete-orphan"` to the relationship definitions, or `ondelete="CASCADE"` to the FK columns.

---

### 19. `backend/agents/execution.py` — Tool results not length-capped before being sent back to LLM

A tool like `github_list_issues` on a repo with 1000 issues will return a massive JSON blob that is fed verbatim back into the LLM context, potentially exceeding the model's context window and causing a 400 error or truncation.

**Fix:** Truncate tool result `data` to a reasonable size (e.g., 8000 chars) before adding it to the message history.

---

### 20. `backend/llm/openrouter_provider.py` — `BadRequestError` retry loop swallows all errors

The `except BadRequestError: continue` in the retry loop catches all `BadRequestError` instances, not just tool-call validation failures. A genuine bad request (malformed message, unsupported parameter) will be silently retried 3 times before falling back to tool-free mode, hiding the real error.

**Fix:** Re-check the error message/code before retrying, similar to the original `_is_tool_use_failure()` pattern in the Groq provider.

---

### 21. `backend/core/hitl.py` — `ACTIVE_APPROVALS` gauge can go negative

`ACTIVE_APPROVALS.dec()` is called on every `record_decision()` regardless of whether the approval was previously counted by `.inc()`. If an approval is recorded outside the normal flow (e.g., direct DB insert), the gauge goes negative.

**Fix:** Only `dec()` if the approval was in `pending` state when fetched, and guard with `max(0, ...)` or use `ACTIVE_APPROVALS.set(count)` from a DB query instead.

---

### 22. `backend/mcp/registry.py` — `build_router()` creates new tool instances on every call

`get_registry().build_router()` is called inside `chat.py` and `deps.py` at module import time — fine. But if called again (e.g., in tests or hot-reload), new tool instances are created, potentially opening duplicate HTTP clients.

**Fix:** Cache the result of `build_router()` with `@lru_cache` or memoize it on the registry instance.

---

### 23-40. Additional HIGH findings (summary)

| # | Location | Issue |
|---|----------|-------|
| 23 | `backend/rag/retriever.py` | Query embeddings not cached — same query re-embeds every call |
| 24 | `backend/agents/planner.py` | Planner prompt includes full tool list — bloats context at 12K TPM limit |
| 25 | `backend/security/guardrails.py` | Regex patterns use `re.search` not `re.fullmatch` — partial matches may miss injections |
| 26 | `backend/workers/tasks.py` | `asyncio.run()` inside Celery task creates new event loop per task — not safe with async DB drivers |
| 27 | `backend/api/routes/runs.py` | No max goal length — 100K char goal passed to LLM burns context |
| 28 | `frontend/src/components/RunDetail.jsx` | Polling every 2s with no exponential backoff — hammers server on long runs |
| 29 | `backend/core/orchestrator.py` | `run()` has no overall timeout — a hung LangGraph node blocks the thread forever |
| 30 | `backend/tools/ops.py` | Sensitive tools return hardcoded success — HITL approval flow never gets real feedback |
| 31 | `backend/rag/store.py` | Qdrant collection created without `on_disk=True` — all vectors in RAM, crashes on large KB |
| 32 | `backend/api/routes/chat.py` | Conversation `title` set to first 50 chars of message — includes potential PII |
| 33 | `backend/agents/reporting.py` | Report concatenates raw tool output — secrets redaction not applied to final report |
| 34 | `backend/db/session.py` | `init_db()` uses `create_all` — dangerous in production, bypasses Alembic migrations |
| 35 | `frontend/src/components/NewRun.jsx` | Goal submitted on Enter key with no debounce — double submission possible |
| 36 | `backend/security/secrets.py` | `redact()` only covers known key patterns — new key formats (OpenRouter `sk-or-v1-*`) not redacted |
| 37 | `backend/api/routes/mcp.py` | `POST /v1/mcp/tools/{name}` passes raw request body dict to `tool.run(**body)` — no argument validation |
| 38 | `backend/core/workflow/graph.py` | Security node runs on every run including re-tries — re-checks already-approved actions |
| 39 | `backend/llm/openrouter_provider.py` | Streaming `tc_acc` index collisions possible if model emits non-sequential tool call indices |
| 40 | `frontend/src/components/Documents.jsx` | File input not reset after upload — same file cannot be re-uploaded without page refresh |

---

## 🟡 MEDIUM (summary)

| # | Location | Issue |
|---|----------|-------|
| 41 | `backend/config.py` | `CRITIC_CONFIDENCE_THRESHOLD` not validated — value > 1.0 causes infinite retry loop |
| 42 | `backend/rag/chunker.py` | Chunk overlap larger than chunk causes infinite loop for very short documents |
| 43 | `backend/agents/critic.py` | `asyncio.gather()` — if one check raises, others' results are discarded |
| 44 | `backend/core/orchestrator.py` | `tool_calls` count in `RunResult` counts attempts not successes |
| 45 | `backend/api/routes/runs.py` | `GET /v1/runs` returns all runs for org — no pagination, unbounded response size |
| 46 | `backend/db/models.py` | UUIDs generated in Python not DB — no guarantee of uniqueness under high concurrency |
| 47 | `backend/tools/rag.py` | `search_documents` returns raw chunk text — no max length cap |
| 48 | `backend/mcp/adapter.py` | `tool_to_spec()` copies tool schema by reference — mutations affect the original |
| 49 | `backend/agents/structured.py` | Retry on schema validation sends full error back to LLM — leaks internal structure |
| 50 | `frontend/src/api.js` | `fetchRuns` and `fetchApprovals` poll on page load — no deduplication if called concurrently |
| 51 | `backend/core/reflection.py` | `should_retry()` only checks confidence — doesn't check if plan actually changed |
| 52 | `backend/workers/schedules.py` | Beat schedule hardcoded to UTC 08:00 — no timezone config for non-UTC deployments |
| 53 | `backend/rag/pipeline.py` | Prompt template inlines all chunk texts — no token budget enforcement |
| 54 | `backend/tools/slack.py` | Mock returns success always — errors in real Slack API never surface |
| 55 | `backend/observability/metrics.py` | `ACTIVE_APPROVALS` gauge not initialised to 0 — first scrape may show no data |
| 56 | `backend/api/deps.py` | `get_orchestrator()` uses `build_default_router()` but chat uses registry router — tool sets differ |
| 57 | `backend/security/secrets.py` | `redact()` applied to tool results only — not to plan steps or research notes sent to LLM |
| 58 | `frontend/src/components/ApprovalPanel.jsx` | No confirmation dialog before Approve — accidental clicks execute sensitive actions |
| 59 | `backend/core/orchestrator.py` | `_pause()` stores full `RunState` in approval payload — may contain sensitive tool results |
| 60 | `backend/llm/base.py` | `chat_stream()` default fallback yields `done` without `tool_calls` key typed correctly |
| 61 | `backend/rag/ingest.py` | `org_id` not stored in Qdrant payload — cross-org RAG leakage if org filter fails |
| 62 | `backend/api/routes/chat.py` | History loaded without limit — old conversations with 1000+ messages burn full context |
| 63 | `backend/agents/execution.py` | Tool error messages returned verbatim to LLM — may contain internal paths/credentials |
| 64 | `frontend/src/components/Chat.jsx` | No max message length enforced client-side — user can paste 1MB text |
| 65 | `backend/core/workflow/graph.py` | `MemorySaver` checkpoint grows unbounded — no TTL or eviction |
| 66 | `backend/tools/monitoring.py` | Mock health check always returns healthy — real infra failures never detected |
| 67 | `backend/mcp/registry.py` | `TOOLS_ENABLED="all"` enables ops tools (rollback, restart) without explicit intent |
| 68 | `backend/rag/store.py` | `hybrid_search()` catches all exceptions silently — Qdrant outage returns empty results, not error |
| 69 | `backend/api/routes/approvals.py` | Completed approval `GET /v1/approvals` returns only pending — no history view |
| 70 | `backend/workers/tasks.py` | Health check task raises on any exception — Celery marks it as failed, no retry |
| 71 | `backend/agents/copilot.py` | System prompt hardcoded — cannot be customised per org or per use case |
| 72 | `backend/core/orchestrator.py` | No run deduplication — same goal submitted twice creates two identical runs |
| 73 | `frontend/src/components/RunList.jsx` | Status badge colours not consistent with `RunDetail.jsx` badge colours |
| 74 | `backend/db/models.py` | `created_at` uses `datetime.utcnow` (deprecated) — use `datetime.now(UTC)` |
| 75 | `backend/config.py` | `REDIS_URL` has no default validation — missing Redis silently breaks Celery with no startup error |

---

## 🟢 LOW (summary)

| # | Location | Issue |
|---|----------|-------|
| 76 | `backend/llm/openrouter_provider.py` | `_EXTRA_HEADERS` hardcodes a GitHub URL as HTTP-Referer |
| 77 | `backend/tools/github.py` | `GitHubCommitsTool` commit message truncated at first `\n` — multiline messages lost |
| 78 | `backend/agents/planner.py` | Plan step `kind` field allows any string — not validated to `research`/`execution` |
| 79 | `frontend/src/App.jsx` | `online-badge` always shows green — no real health check to backend |
| 80 | `backend/security/guardrails.py` | Patterns are case-insensitive but test suite doesn't cover mixed-case injections |
| 81 | `backend/rag/extract.py` | PDF extraction swallows `PdfReadError` — corrupted PDF returns empty string silently |
| 82 | `backend/api/routes/mcp.py` | Tool discovery endpoint `GET /v1/mcp/tools` has no caching — re-builds on every request |
| 83 | `backend/core/orchestrator.py` | `run_id` logged but not included in structured log fields — hard to correlate in Grafana |
| 84 | `backend/config.py` | `LOG_LEVEL` setting read but never applied to Python `logging` module |
| 85 | `frontend/src/components/ToolsPanel.jsx` | `SERVER_COLORS` dict missing entries for new servers — falls back to grey silently |
| 86 | `backend/agents/reporting.py` | Report sources list not deduplicated — same source appears multiple times |
| 87 | `backend/workers/celery_app.py` | Celery `hard_time_limit=600` — longer runs killed mid-execution with no cleanup |
| 88 | `backend/mcp/servers/` | Server `name` attributes not validated for uniqueness — duplicate names silently overwrite |
| 89 | `frontend/src/components/NewRun.jsx` | Suggestion chips not localised — hardcoded English strings |
| 90 | `backend/rag/retriever.py` | `top_k` defaulted from `settings.RAG_TOP_K` — no per-request override exposed in `/ask` |
| 91 | `backend/tools/web_search.py` | Mock note "simulated" returned in data — leaks implementation detail to LLM |
| 92 | `backend/db/models.py` | `Document.source` column has no uniqueness constraint — same file ingested twice creates duplicates |
| 93 | `backend/api/routes/chat.py` | Conversation `title` never updated after first message — stays as first 50 chars forever |
| 94 | `frontend/src/components/Documents.jsx` | Citation `score` shown as raw float (e.g., `0.823412`) — should be rounded |
| 95 | `backend/observability/tracing.py` | `init_tracing()` sets env vars as side effects — not idempotent if called twice |
| 96 | `backend/config.py` | `APP_HOST=0.0.0.0` default — binds to all interfaces, not just localhost in dev |

---

## Top 3 Fix Immediately

1. 🔴 **RBAC header spoofing** (`security/rbac.py`) — koi bhi admin ban sakta hai, production mein catastrophic
2. 🔴 **Documents endpoints no auth** (`routes/documents.py`) — anonymous LLM credit drain + data exfiltration
3. 🔴 **GitHub SSRF** (`tools/github.py`) — model-generated URL injection via `repo` parameter

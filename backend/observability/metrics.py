"""
Prometheus metrics for the AI Operations Copilot.

All metrics are module-level singletons — import and increment them from
wherever the event happens (orchestrator, LLM provider, route handlers).

Exposed at GET /metrics (mounted as an ASGI sub-app in main.py).

Metrics:
  copilot_runs_total{status}           — runs by outcome
  copilot_run_duration_seconds         — end-to-end latency histogram
  copilot_tool_calls_total{tool,ok}    — tool invocations
  copilot_active_approvals             — pending HITL approvals (gauge)
  copilot_llm_requests_total{provider} — LLM API calls
  copilot_llm_tokens_total{kind}       — prompt / completion tokens
  copilot_critic_retries_total         — Critic-driven retry loops
"""
from prometheus_client import Counter, Gauge, Histogram

RUNS_TOTAL = Counter(
    "copilot_runs_total",
    "Total multi-agent runs, labelled by final status.",
    ["status"],  # completed | failed | awaiting_approval
)

RUN_DURATION = Histogram(
    "copilot_run_duration_seconds",
    "End-to-end run wall-clock time in seconds.",
    buckets=[5, 15, 30, 60, 120, 300, 600],
)

TOOL_CALLS_TOTAL = Counter(
    "copilot_tool_calls_total",
    "Tool calls made by the Execution agent.",
    ["tool_name", "ok"],  # ok: "true" | "false"
)

ACTIVE_APPROVALS = Gauge(
    "copilot_active_approvals",
    "Number of HITL approvals currently in 'pending' state.",
)
ACTIVE_APPROVALS.set(0)  # ensure the gauge appears in first scrape, not as NaN

LLM_REQUESTS_TOTAL = Counter(
    "copilot_llm_requests_total",
    "LLM chat-completion API requests.",
    ["provider"],  # groq | openai | anthropic
)

LLM_TOKENS_TOTAL = Counter(
    "copilot_llm_tokens_total",
    "LLM tokens consumed.",
    ["kind"],  # prompt | completion
)

CRITIC_RETRIES_TOTAL = Counter(
    "copilot_critic_retries_total",
    "Times the Critic triggered a retry loop.",
)

"""
Dynamic system-prompt builder.

Two responsibilities:
1. build_system_prompt(tool_names)  — called once at agent init; decides WHICH
   sections are available based on registered tools.
2. build_prompt_for_turn(messages)  — called every turn; scans the last few
   messages for service keywords and injects only the relevant sections.
"""
from backend.prompts.base import BASE_PROMPT
from backend.prompts.sections.github import GITHUB_SECTION
from backend.prompts.sections.slack import SLACK_SECTION
from backend.prompts.sections.rag import RAG_SECTION
from backend.prompts.sections.ops import OPS_SECTION
from backend.prompts.sections.monitoring import MONITORING_SECTION
from backend.prompts.sections.workflows import WORKFLOWS_SECTION

# ── 1. Tool-presence map ──────────────────────────────────────────────────────
# Which tool-name substring → which section
_TOOL_TRIGGERS: list[tuple[str, str]] = [
    ("github",              GITHUB_SECTION),
    ("slack",               SLACK_SECTION),
    ("search_documents",    RAG_SECTION),
    ("rollback_deployment", OPS_SECTION),
    ("restart_service",     OPS_SECTION),
    ("get_service_health",  MONITORING_SECTION),
    ("get_metrics",         MONITORING_SECTION),
    ("generate_standup",    WORKFLOWS_SECTION),
    ("notify_stale_prs",    WORKFLOWS_SECTION),
    ("broadcast_incident",  WORKFLOWS_SECTION),
    ("notify_pr_stake",     WORKFLOWS_SECTION),
]

# ── 2. Keyword map ────────────────────────────────────────────────────────────
# Which user-message keywords → which section
_KEYWORD_MAP: list[tuple[frozenset[str], str]] = [
    (frozenset([
        "github", "repo", "repository", "pull request", "pull requests",
        "commit", "commits", "branch", "branches", "merge pr", "merge branch",
        "open issue", "close issue", "create issue", "list issues",
        "fork", "release", "releases", "workflow run", "github actions",
        "code review", "milestone", "contributor", "readme",
    ]), GITHUB_SECTION),

    (frozenset([
        "slack", "channel", "channels", "direct message",
        "post message", "send message", "dm to", "send dm",
        "notify", "notification", "slack message",
        "thread", "reaction", "pin message", "invite to channel",
        "workspace", "@here", "@channel",
    ]), SLACK_SECTION),

    (frozenset([
        "document", "documents", "search docs", "search document",
        "pdf", "wiki", "runbook", "knowledge base", "find in docs",
        "search knowledge", "policy", "policies", "handbook",
    ]), RAG_SECTION),

    (frozenset([
        "restart service", "restart the", "rollback", "roll back",
        "deploy", "deployment", "rollout", "service down",
        "bring down", "bring up", "revert deploy",
    ]), OPS_SECTION),

    (frozenset([
        "standup", "stand up", "daily summary", "morning report",
        "stale pr", "pr reminder", "review reminder", "chase reviewers",
        "incident", "production down", "prod down", "outage",
        "notify everyone", "pr stakeholders", "notify pr",
        "pr merged", "notify team", "broadcast incident",
    ]), WORKFLOWS_SECTION),

    (frozenset([
        "service health", "check health", "metrics", "cpu usage",
        "memory usage", "latency", "uptime", "error rate",
        "throughput", "p95", "p99", "monitoring dashboard",
    ]), MONITORING_SECTION),
]


def _available_sections(tool_names: list[str]) -> set[str]:
    """Sections whose backing tools are actually registered."""
    available: set[str] = set()
    for trigger, section in _TOOL_TRIGGERS:
        if any(trigger in name for name in tool_names):
            available.add(section)
    return available


def build_system_prompt(tool_names: list[str]) -> str:
    """
    Called once at CopilotAgent init.
    Stores available sections on the agent; returns base-only prompt.
    The per-turn injector (build_prompt_for_turn) does the real work.
    """
    # Return just the base — sections are injected per-turn.
    return BASE_PROMPT


def detect_sections(messages: list[dict], available: set[str]) -> list[str]:
    """
    Scan the last 4 messages for service keywords.
    Returns the list of section texts that should be injected this turn.
    Falls back to ALL available sections if nothing is detected.
    """
    # Combine text of last 4 messages (user + assistant) for context window
    window = " ".join(
        m.get("content") or ""
        for m in messages[-4:]
        if isinstance(m.get("content"), str)
    ).lower()

    detected: list[str] = []
    seen: set[str] = set()

    for keywords, section in _KEYWORD_MAP:
        if section not in available or section in seen:
            continue
        if any(kw in window for kw in keywords):
            detected.append(section)
            seen.add(section)

    # Nothing matched → inject everything available (safe fallback)
    if not detected:
        return [s for s in [
            GITHUB_SECTION, SLACK_SECTION, RAG_SECTION,
            OPS_SECTION, MONITORING_SECTION,
        ] if s in available]

    return detected


def build_prompt_for_turn(base: str, messages: list[dict], available: set[str]) -> str:
    """Build the full system prompt for this specific turn."""
    sections = detect_sections(messages, available)
    if sections:
        return base + "\n" + "\n".join(sections)
    return base

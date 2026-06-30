"""
Dynamic system-prompt builder.

Two responsibilities:
1. _available_sections(tool_names)  — called once at agent init; decides WHICH
   sections are available based on registered tools.
2. build_prompt_for_turn(messages)  — called every turn; asks a small free LLM
   which services are relevant and injects only those sections.
"""
import json
import logging

import httpx

from backend.prompts.base import BASE_PROMPT
from backend.prompts.sections.github import GITHUB_SECTION
from backend.prompts.sections.slack import SLACK_SECTION
from backend.prompts.sections.rag import RAG_SECTION
from backend.prompts.sections.ops import OPS_SECTION
from backend.prompts.sections.monitoring import MONITORING_SECTION
from backend.prompts.sections.workflows import WORKFLOWS_SECTION

logger = logging.getLogger("copilot.prompt_builder")

BUILD_PROMPT_USER_PREFIX = "The user's name is {user_name}. Address them by name when appropriate.\n\n"

# ── Tool-presence map ─────────────────────────────────────────────────────────
# Which tool-name substring → which section label
_TOOL_TRIGGERS: list[tuple[str, str]] = [
    ("github",              "github"),
    ("slack",               "slack"),
    ("search_documents",    "rag"),
    ("rollback_deployment", "ops"),
    ("restart_service",     "ops"),
    ("get_service_health",  "monitoring"),
    ("get_metrics",         "monitoring"),
    ("generate_standup",    "workflows"),
    ("notify_stale_prs",    "workflows"),
    ("broadcast_incident",  "workflows"),
    ("notify_pr_stake",     "workflows"),
]

# Label → actual prompt section text
_SECTION_TEXT: dict[str, str] = {
    "github":     GITHUB_SECTION,
    "slack":      SLACK_SECTION,
    "rag":        RAG_SECTION,
    "ops":        OPS_SECTION,
    "monitoring": MONITORING_SECTION,
    "workflows":  WORKFLOWS_SECTION,
}

_CLASSIFIER_PROMPT = """\
You are a routing classifier for an AI assistant.

Read the conversation below and return a JSON array of which service domains are \
being discussed or needed. Return ONLY the JSON array — no explanation, no markdown.

Available domains: {available}

Rules:
- Return [] if the user is asking a general question (greetings, math, writing, etc.)
- Return ["slack"] if the user wants to send a message, DM, notify someone, or post anything on Slack
- Return ["github"] if the user mentions repos, PRs, commits, issues, branches
- Return ["rag"] if the user wants to search documents, wikis, runbooks, or uploaded files
- Return ["ops"] if the user mentions deployments, rollbacks, restarting services
- Return ["monitoring"] if the user asks about health, metrics, latency, CPU, uptime
- Return ["workflows"] if the user mentions standups, incident broadcast, PR reminders
- You may return multiple domains if the request spans more than one
- Use the full conversation context — if the user said "on slack please" after an earlier message, include "slack"

Conversation:
{messages}

JSON array:"""


def _available_sections(tool_names: list[str]) -> set[str]:
    """Sections whose backing tools are actually registered."""
    available: set[str] = set()
    for trigger, label in _TOOL_TRIGGERS:
        if any(trigger in name for name in tool_names):
            available.add(label)
    return available


def build_system_prompt(tool_names: list[str]) -> str:
    """Called once at CopilotAgent init. Returns base-only prompt."""
    return BASE_PROMPT


async def detect_sections_llm(messages: list[dict], available: set[str]) -> list[str]:
    """
    Ask a small free LLM which service sections are needed for this turn.
    Falls back to all available sections on any error (never silently breaks the agent).
    """
    from backend.config import settings

    if not settings.OPENROUTER_API_KEY:
        return list(available)

    # Build a short conversation snippet (last 5 turns, 300 chars each)
    lines = []
    for m in messages[-5:]:
        role    = m.get("role", "user")
        content = (m.get("content") or "")[:300]
        lines.append(f"{role}: {content}")
    convo = "\n".join(lines)

    prompt = _CLASSIFIER_PROMPT.format(
        available=", ".join(sorted(available)),
        messages=convo,
    )

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":      settings.CLASSIFIER_MODEL,
                    "messages":   [{"role": "user", "content": prompt}],
                    "max_tokens": 60,
                    "temperature": 0,
                },
            )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()

        # Parse JSON array from response
        detected: list[str] = json.loads(raw)
        if not isinstance(detected, list):
            raise ValueError("not a list")

        # Keep only labels that are actually available
        valid = [lbl for lbl in detected if lbl in available]
        logger.debug("Classifier detected sections: %s", valid)
        return valid if valid else list(available)

    except Exception as exc:
        logger.warning("Section classifier failed (%s) — injecting all sections", exc)
        return list(available)


async def build_prompt_for_turn(base: str, messages: list[dict], available: set[str]) -> str:
    """Build the full system prompt for this specific turn."""
    if not available:
        return base

    labels  = await detect_sections_llm(messages, available)
    sections = [_SECTION_TEXT[lbl] for lbl in labels if lbl in _SECTION_TEXT]

    if sections:
        return base + "\n" + "\n".join(sections)
    return base

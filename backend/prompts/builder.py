"""
Dynamic system-prompt builder.

Assembles a prompt from the base + only the domain sections
that match the tools actually registered in the router.
"""
from backend.prompts.base import BASE_PROMPT
from backend.prompts.sections.github import GITHUB_SECTION
from backend.prompts.sections.slack import SLACK_SECTION
from backend.prompts.sections.rag import RAG_SECTION
from backend.prompts.sections.ops import OPS_SECTION
from backend.prompts.sections.monitoring import MONITORING_SECTION

# Each entry: (trigger_substring, section_text)
# A section is included when ANY registered tool name contains the trigger.
_SECTIONS: list[tuple[str, str]] = [
    ("github",              GITHUB_SECTION),
    ("slack",               SLACK_SECTION),
    ("search_documents",    RAG_SECTION),
    ("rollback_deployment", OPS_SECTION),
    ("restart_service",     OPS_SECTION),
    ("get_service_health",  MONITORING_SECTION),
    ("get_metrics",         MONITORING_SECTION),
]


def build_system_prompt(tool_names: list[str]) -> str:
    """Return a system prompt tailored to the given set of tool names."""
    seen: set[str] = set()
    sections: list[str] = []

    for trigger, section in _SECTIONS:
        if section in seen:
            continue
        if any(trigger in name for name in tool_names):
            sections.append(section)
            seen.add(section)

    if sections:
        return BASE_PROMPT + "\n" + "\n".join(sections)
    return BASE_PROMPT

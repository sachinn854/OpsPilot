"""
Prompt-injection guardrails.

Scans user-supplied text for known injection patterns before it reaches the
LLM. Returns a GuardResult — callers decide what to do (raise HTTP 400, log,
silently drop, etc.). No LLM call is made here; purely deterministic regex.
"""
import re
from dataclasses import dataclass, field


@dataclass
class GuardResult:
    safe: bool
    reason: str = field(default="")


# (label, compiled pattern) pairs checked in order.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "ignore_instructions",
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    ),
    (
        "you_are_now",
        re.compile(r"you\s+are\s+now\s+(a\b|an\b)", re.I),
    ),
    (
        "act_as",
        re.compile(r"\bact\s+as\s+(a\b|an\b)", re.I),
    ),
    (
        "pretend_to_be",
        re.compile(r"pretend\s+(to\s+be|you\s+are)", re.I),
    ),
    (
        "jailbreak",
        re.compile(r"\bjailbreak\b", re.I),
    ),
    (
        "dan_mode",
        re.compile(r"\bDAN\s+mode\b", re.I),
    ),
    (
        "forget_instructions",
        re.compile(r"forget\s+(everything|all\s+instructions)", re.I),
    ),
    (
        "new_instructions",
        re.compile(r"new\s+instructions\s*:", re.I),
    ),
    (
        "system_tag",
        re.compile(r"\[SYSTEM\]", re.I),
    ),
    (
        "system_xml",
        re.compile(r"<\s*system\s*>", re.I),
    ),
    (
        "role_spoof",
        re.compile(r"\n\s*(Human|Assistant|System)\s*:", re.I),
    ),
]


def check_injection(text: str) -> GuardResult:
    """Return GuardResult(safe=False, reason=...) if injection is detected."""
    for label, pattern in _PATTERNS:
        if pattern.search(text):
            return GuardResult(
                safe=False,
                reason=f"Potential prompt injection detected ({label})",
            )
    return GuardResult(safe=True)

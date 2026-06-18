"""
Secret redaction.

Call redact() on any text before it is logged or passed to an LLM.
Covers common API key / token formats — not an exhaustive scanner, but
catches the patterns most likely to leak in a copilot context.
"""
import re


# (label, pattern) — label appears in the [REDACTED:<label>] placeholder.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("groq_key",     re.compile(r"gsk_[A-Za-z0-9]{48,}")),
    ("openai_key",   re.compile(r"sk-[A-Za-z0-9\-_]{20,}")),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("github_pat",   re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("aws_key",      re.compile(r"AKIA[A-Z0-9]{16}")),
    ("bearer",       re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_\.]{16,}")),
    ("password_kv",  re.compile(r"(?i)password\s*[=:]\s*\S+")),
]


def redact(text: str) -> str:
    """Replace known secret patterns with [REDACTED:<type>] placeholders."""
    for label, pattern in _PATTERNS:
        text = pattern.sub(f"[REDACTED:{label}]", text)
    return text

"""
LangSmith tracing initialisation.

LangGraph traces all agent steps automatically when these environment variables
are present:
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=<your LangSmith key>
    LANGCHAIN_PROJECT=<project name>

This module reads LANGSMITH_API_KEY + LANGSMITH_PROJECT from our config and
sets the LangChain vars at startup. Nothing breaks if the key is absent —
tracing is simply disabled.

How to enable:
    1. Get a free key at https://smith.langchain.com
    2. Add to .env:
           LANGSMITH_API_KEY=lsv2_...
           LANGSMITH_PROJECT=ai-operations-copilot
    3. Restart the server — traces appear in the LangSmith UI instantly.
"""
import logging
import os

logger = logging.getLogger("copilot.tracing")


def init_tracing() -> bool:
    """Enable LangSmith tracing if LANGSMITH_API_KEY is configured.

    Returns True when tracing was activated, False when the key is absent.
    Safe to call multiple times (idempotent).
    """
    api_key = os.getenv("LANGSMITH_API_KEY", "").strip()
    if not api_key:
        logger.info("LangSmith tracing disabled (LANGSMITH_API_KEY not set).")
        return False

    project = os.getenv("LANGSMITH_PROJECT", "ai-operations-copilot")

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGCHAIN_PROJECT"] = project

    logger.info("LangSmith tracing enabled → project: '%s'", project)
    return True

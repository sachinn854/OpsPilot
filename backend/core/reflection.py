"""
Reflection gate (Phase 3).

The self-correction logic that decides, after the Critic has spoken, whether the
run is good enough to report or should loop back and try again. Kept in one place
so the policy (confidence threshold, retry budget) is easy to read and tune.
"""
from typing import Literal

from backend.config import settings
from backend.core.workflow.state import RunState

Decision = Literal["retry", "report"]


def should_retry(state: RunState) -> Decision:
    """Return "report" if the work passes (or we're out of retries), else "retry"."""
    verdict = state.get("verdict")
    attempts = state.get("attempts", 0)

    if verdict is not None:
        good = verdict.passed and verdict.confidence >= settings.CRITIC_CONFIDENCE_THRESHOLD
        if good:
            return "report"

    # `attempts` = number of Critic evaluations so far (incremented in the critic
    # node). The first pass is attempt 1; RUN_MAX_RETRIES additional loops are
    # allowed, so we stop once attempts exceeds the budget.
    if attempts > settings.RUN_MAX_RETRIES:
        return "report"  # out of budget — report the best we have

    return "retry"

"""
Critic agent — multi-check verification.

Runs three independent LLM checks (correctness, completeness, safety) then
aggregates them into a single Verdict. This catches failure modes that a
single-pass critic misses: an answer can be correct but incomplete, or
complete but hallucinated.

Aggregation rules:
  - passed   = all three checks passed
  - confidence = average of individual confidences
  - feedback = concatenation of any non-empty check notes
"""
import asyncio

from pydantic import BaseModel, Field

from backend.agents.base import BaseAgent
from backend.agents.structured import complete_structured
from backend.llm.base import LLMProvider

_CHECK_TEMPLATE = """You are verifying one specific dimension of an AI agent's output.

Goal: {goal}

Research notes:
{research_notes}

Execution output:
{execution_output}

Your dimension: **{dimension}**

{dimension_instructions}

Return JSON:
- passed: true if this dimension is satisfied.
- confidence: 0.0–1.0 certainty.
- notes: specific issues found (empty string if none)."""

_DIMENSIONS = {
    "correctness": (
        "Check whether every factual claim in the execution output is grounded in the "
        "research notes or tool results — nothing invented or hallucinated."
    ),
    "completeness": (
        "Check whether the execution output FULLY addresses the goal — all sub-questions "
        "answered, no missing steps, no unexplained gaps."
    ),
    "safety": (
        "Check that the output contains no leaked secrets, PII, credentials, or "
        "instructions that could harm the user or system."
    ),
}


class CriticCheck(BaseModel):
    passed: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    notes: str = ""


class Verdict(BaseModel):
    passed: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    feedback: str = ""
    checks: list[dict] = Field(default_factory=list)


class CriticAgent(BaseAgent):
    def __init__(self, llm: LLMProvider):
        super().__init__(llm, "")  # system prompt is per-check

    async def _run_check(
        self, goal: str, research_notes: str, execution_output: str, dimension: str
    ) -> CriticCheck:
        instructions = _DIMENSIONS[dimension]
        prompt = _CHECK_TEMPLATE.format(
            goal=goal,
            research_notes=research_notes,
            execution_output=execution_output,
            dimension=dimension,
            dimension_instructions=instructions,
        )
        messages = [{"role": "user", "content": prompt}]
        return await complete_structured(self.llm, messages, CriticCheck)

    async def run(
        self, goal: str, *, research_notes: str, execution_output: str
    ) -> Verdict:
        """Run all three checks concurrently and aggregate into a Verdict."""
        results = await asyncio.gather(
            self._run_check(goal, research_notes, execution_output, "correctness"),
            self._run_check(goal, research_notes, execution_output, "completeness"),
            self._run_check(goal, research_notes, execution_output, "safety"),
            return_exceptions=True,
        )

        checks: list[CriticCheck] = []
        for dim, r in zip(_DIMENSIONS.keys(), results):
            if isinstance(r, Exception):
                # If a check errors, treat it as a low-confidence failure.
                checks.append(CriticCheck(passed=False, confidence=0.3, notes=str(r)))
            else:
                checks.append(r)

        passed = all(c.passed for c in checks)
        confidence = sum(c.confidence for c in checks) / len(checks)
        feedback = " | ".join(
            f"{dim}: {c.notes}"
            for dim, c in zip(_DIMENSIONS.keys(), checks)
            if c.notes
        )

        return Verdict(
            passed=passed,
            confidence=round(confidence, 3),
            feedback=feedback,
            checks=[
                {"dimension": dim, "passed": c.passed, "confidence": c.confidence, "notes": c.notes}
                for dim, c in zip(_DIMENSIONS.keys(), checks)
            ],
        )

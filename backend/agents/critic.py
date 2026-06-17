"""
Critic agent (Phase 3).

The self-correction gate. It inspects the goal, the research, and the execution
output and judges whether the goal is actually satisfied — returning a typed
`Verdict` with a confidence score and concrete feedback. The orchestrator uses
this to decide whether to report the result or loop back and try again.
"""
from pydantic import BaseModel, Field

from backend.agents.base import BaseAgent
from backend.agents.structured import complete_structured
from backend.llm.base import LLMProvider

CRITIC_PROMPT = """You are the Critic in a multi-agent operations copilot.

Judge whether the work actually satisfies the goal. Be strict and skeptical:
- Is the goal fully addressed by the evidence (research + execution results)?
- Are claims grounded in tool results / retrieved context, not invented?
- Is anything missing, contradictory, or unsupported?

Return JSON with:
- passed: true only if the goal is genuinely satisfied.
- confidence: 0.0-1.0, how sure you are the output is correct and complete.
- feedback: specific, actionable notes on what to fix (empty if passed cleanly)."""


class Verdict(BaseModel):
    passed: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    feedback: str = ""


class CriticAgent(BaseAgent):
    def __init__(self, llm: LLMProvider):
        super().__init__(llm, CRITIC_PROMPT)

    async def run(
        self, goal: str, *, research_notes: str, execution_output: str
    ) -> Verdict:
        """Evaluate the work and return a typed verdict."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Goal: {goal}\n\nResearch notes:\n{research_notes}\n\n"
                    f"Execution output:\n{execution_output}"
                ),
            },
        ]
        return await complete_structured(self.llm, messages, Verdict)

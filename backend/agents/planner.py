"""
Planner agent.

Takes a high-level goal and breaks it into an ordered list of concrete steps.
Each step is tagged as either:
  - "research"  → needs information gathering (RAG / memory), or
  - "execution" → needs an action via a tool (GitHub, etc.).

Output is a typed `Plan` (Pydantic), so downstream agents consume structure,
not prose.
"""
from typing import Literal

from pydantic import BaseModel, Field

from backend.agents.base import BaseAgent
from backend.agents.structured import complete_structured
from backend.llm.base import LLMProvider

PLANNER_PROMPT = """You are the Planner in a multi-agent operations copilot.

Break the user's goal into a short ordered list of concrete steps (2-5 steps).
For each step decide its kind:
  - "research"  : gather information / context (documents, memory, logs).
  - "execution" : perform an action using a tool (e.g. fetch GitHub issues).

Keep steps minimal and non-overlapping. Do not invent details not implied by the
goal. Return the plan as JSON."""


class PlanStep(BaseModel):
    description: str = Field(..., description="What this step accomplishes.")
    kind: Literal["research", "execution"] = "research"


class Plan(BaseModel):
    goal: str
    steps: list[PlanStep]


class PlannerAgent(BaseAgent):
    def __init__(self, llm: LLMProvider):
        super().__init__(llm, PLANNER_PROMPT)

    async def run(self, goal: str, *, feedback: str | None = None) -> Plan:
        """Produce a typed plan for `goal`. `feedback` (from the Critic) refines a retry."""
        user = f"Goal: {goal}"
        if feedback:
            user += (
                f"\n\nThe previous attempt was insufficient. Critic feedback: "
                f"{feedback}\nRevise the plan to address it."
            )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user},
        ]
        plan = await complete_structured(self.llm, messages, Plan)
        # Ensure the goal is always carried even if the model omits/alters it.
        plan.goal = goal
        return plan

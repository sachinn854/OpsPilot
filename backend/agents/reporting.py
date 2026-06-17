"""
Reporting agent.

The final stage. It composes a clear, human-facing answer from everything the
pipeline produced — research, execution results, and the Critic's verdict —
including the evidence (sources / tool results) so the answer is traceable.
"""
from backend.agents.base import BaseAgent
from backend.llm.base import LLMProvider

REPORTING_PROMPT = """You are the Reporting agent in a multi-agent operations copilot.

Write the final answer to the user's goal using only the provided research and
execution results. Be clear and well-structured:
- Lead with the direct answer / outcome.
- Support it with the key evidence (cite sources or tool results).
- If confidence is low or something is unresolved, say so honestly.
Do not introduce new facts that aren't in the inputs."""


class ReportingAgent(BaseAgent):
    def __init__(self, llm: LLMProvider):
        super().__init__(llm, REPORTING_PROMPT)

    async def run(
        self,
        goal: str,
        *,
        research_notes: str,
        execution_output: str,
        confidence: float,
        sources: list[str],
    ) -> str:
        """Compose the final report text."""
        src = ", ".join(sources) if sources else "none"
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Goal: {goal}\n\nResearch notes:\n{research_notes}\n\n"
                    f"Execution output:\n{execution_output}\n\n"
                    f"Critic confidence: {confidence:.2f}\nSources: {src}"
                ),
            },
        ]
        response = await self.llm.chat(messages)
        return response.content or ""

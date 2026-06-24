"""
Reporting agent.

The final stage. It composes a clear, human-facing answer from everything the
pipeline produced — research, execution results, and the Critic's verdict —
including the evidence (sources / tool results) so the answer is traceable.
"""
from backend.agents.base import BaseAgent
from backend.llm.base import LLMProvider
from backend.security.secrets import redact

REPORTING_PROMPT = """You are the Reporting agent in a multi-agent operations copilot.

Write the final answer to the user's goal using only the provided research and execution results.

Rules:
- Write in plain English prose only. No JSON, no code blocks, no markdown tables.
- Lead with the direct answer in one sentence.
- Then add supporting detail in 2-3 short sentences.
- Use EXACT names, titles, numbers from the execution output — never paraphrase or invent them.
- If confidence is low or something is unresolved, say so honestly.
- Never invent facts not present in the inputs."""


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
        # Redact secrets before they reach the LLM or appear in the final report.
        safe_execution = redact(execution_output)
        safe_research = redact(research_notes)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Goal: {goal}\n\nResearch notes:\n{safe_research}\n\n"
                    f"Execution output:\n{safe_execution}\n\n"
                    f"Critic confidence: {confidence:.2f}\nSources: {src}"
                ),
            },
        ]
        response = await self.llm.chat(messages)
        return response.content or ""

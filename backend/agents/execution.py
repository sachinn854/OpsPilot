"""
Execution agent.

Carries out the plan's actions by calling tools through the Tool Router — the
same tool-calling loop the Copilot used, but now one specialized stage
in the graph. It is given the goal, the plan, and the research notes, and it
returns what it did plus a structured log of every tool call (for the `runs` /
`tool_calls` audit trail).
"""
import json

from pydantic import BaseModel

from backend.agents.base import BaseAgent
from backend.core.tool_router import ToolRouter
from backend.llm.base import LLMProvider

EXECUTION_PROMPT = """You are the Execution agent in a multi-agent operations copilot.

You are given a goal, a plan, and research notes. Use the available tools to carry
out the plan's actions and collect the concrete results needed to satisfy the goal.

Guidelines:
- Call a tool whenever live data or an action is required (e.g. GitHub issues).
- A repository must be 'owner/name'. If required info is missing, state what's missing.
- Base everything ONLY on tool results and the research notes. Never invent data.
- When done, briefly summarize what you found/did."""


class ToolCallLog(BaseModel):
    tool_name: str
    arguments: dict
    ok: bool
    result: dict


class ExecutionResult(BaseModel):
    output: str
    tool_calls: list[ToolCallLog]


class ExecutionAgent(BaseAgent):
    def __init__(
        self, llm: LLMProvider, router: ToolRouter, max_iterations: int = 5
    ):
        super().__init__(llm, EXECUTION_PROMPT)
        self.router = router
        self.max_iterations = max_iterations

    async def run(
        self, goal: str, *, plan_text: str, research_notes: str
    ) -> ExecutionResult:
        """Run the tool-calling loop and return the result + a tool-call log."""
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Goal: {goal}\n\nPlan:\n{plan_text}\n\n"
                    f"Research notes:\n{research_notes}"
                ),
            },
        ]
        tool_schemas = self.router.schemas()
        call_log: list[ToolCallLog] = []

        for _ in range(self.max_iterations):
            response = await self.llm.chat(messages, tools=tool_schemas)

            if not response.wants_tools:
                return ExecutionResult(
                    output=response.content or "", tool_calls=call_log
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in response.tool_calls
                    ],
                }
            )

            for tc in response.tool_calls:
                result = await self.router.execute(tc.name, tc.arguments)
                result_data = result.model_dump()
                call_log.append(
                    ToolCallLog(
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        ok=result.ok,
                        result=result_data,
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result_data),
                    }
                )

        # Hit the iteration cap — summarize with what we have.
        final = await self.llm.chat(messages)
        return ExecutionResult(
            output=final.content
            or "Reached the step limit before fully completing the actions.",
            tool_calls=call_log,
        )

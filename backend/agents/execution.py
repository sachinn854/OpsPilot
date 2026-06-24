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
from backend.security.secrets import redact

def _compact_schemas(schemas: list[dict]) -> list[dict]:
    """Trim verbose descriptions to cut token usage on Groq's free tier."""
    result = []
    for s in schemas:
        fn = s.get("function", {})
        trimmed = dict(fn)
        if desc := trimmed.get("description", ""):
            trimmed["description"] = desc[:120]
        result.append({"type": "function", "function": trimmed})
    return result


def _compress_result(tool_name: str, result_data: dict) -> str:
    """Convert a raw tool result dict to a compact plain-English string.

    Sending full JSON back to the LLM wastes tokens. We extract only the
    meaningful fields and format them as a short readable summary.
    """
    if not result_data.get("ok"):
        return f"Tool {tool_name} failed: {result_data.get('error', 'unknown error')}"

    data = result_data.get("data")
    if data is None:
        return f"Tool {tool_name} succeeded with no data."

    # List of items (e.g. GitHub issues) — summarise each as one line.
    if isinstance(data, list):
        if not data:
            return f"Tool {tool_name} returned 0 results."
        lines = []
        for i, item in enumerate(data[:10], 1):  # cap at 10 items
            if isinstance(item, dict):
                # Pick the most descriptive fields available.
                title = item.get("title") or item.get("name") or item.get("message") or ""
                state = item.get("state") or item.get("status") or ""
                num   = item.get("number") or item.get("id") or ""
                parts = [p for p in [f"#{num}" if num else "", title, f"[{state}]" if state else ""] if p]
                lines.append(f"{i}. {' '.join(parts)}" if parts else f"{i}. {str(item)[:80]}")
            else:
                lines.append(f"{i}. {str(item)[:80]}")
        suffix = f" (showing 10 of {len(data)})" if len(data) > 10 else ""
        return f"Tool {tool_name} returned {len(data)} result(s){suffix}:\n" + "\n".join(lines)

    # Single dict result — flatten key: value pairs, skip long nested objects.
    if isinstance(data, dict):
        pairs = []
        for k, v in data.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                pairs.append(f"{k}: {v}")
            elif isinstance(v, list):
                pairs.append(f"{k}: [{len(v)} items]")
        return f"Tool {tool_name} result: " + ", ".join(pairs[:15])

    # Scalar or string — just truncate.
    return f"Tool {tool_name} result: {str(data)[:300]}"


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
        tool_schemas = _compact_schemas(self.router.schemas())
        call_log: list[ToolCallLog] = []

        raw_results: list[str] = []  # verbatim compressed tool results, not LLM summary

        for _ in range(self.max_iterations):
            response = await self.llm.chat(messages, tools=tool_schemas)

            if not response.wants_tools:
                # Prepend the raw tool results so downstream agents see exact data,
                # then append the LLM's prose summary for context.
                raw_block = "\n".join(raw_results)
                llm_summary = response.content or ""
                combined = f"{raw_block}\n\n{llm_summary}".strip() if raw_block else llm_summary
                return ExecutionResult(output=combined, tool_calls=call_log)

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
                compressed = redact(_compress_result(tc.name, result_data))
                call_log.append(
                    ToolCallLog(
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        ok=result.ok,
                        result=result_data,
                    )
                )
                raw_results.append(f"[{tc.name}] {compressed}")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": compressed,
                    }
                )

        # Hit the iteration cap — summarize with what we have.
        final = await self.llm.chat(messages)
        return ExecutionResult(
            output=final.content
            or "Reached the step limit before fully completing the actions.",
            tool_calls=call_log,
        )

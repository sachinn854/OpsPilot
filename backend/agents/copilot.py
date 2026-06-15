"""
Copilot agent (Phase 1) — a single agent with a tool-calling loop.

Flow:
  1. Send conversation + available tool schemas to the LLM.
  2. If the LLM asks to call tools, run them via the Tool Router and feed the
     results back.
  3. Repeat until the LLM returns a normal answer (or we hit the step limit).

This is the seed of the multi-agent system: in Phase 3 this single loop is split
into Planner → Research → Execution → Critic.
"""
import json

from backend.agents.base import BaseAgent
from backend.core.tool_router import ToolRouter
from backend.llm.base import LLMProvider

SYSTEM_PROMPT = """You are AI Operations Copilot, an autonomous enterprise assistant.

You help engineers with operational tasks: investigating issues, summarizing
GitHub activity, and answering questions. You can call tools to fetch live data.

Guidelines:
- When a question needs live data (e.g. GitHub issues/commits), call the right tool.
- A repository must be given as 'owner/name'. If it's missing, ask the user for it.
- Base your answers ONLY on tool results. NEVER invent issue numbers, commit
  hashes, or any data. If a tool returns an empty list or an error, say so plainly
  (e.g. "No open issues found" or report the error) — do not make up results.
- Be concise and clear. Summarize results in a helpful, structured way.
"""


class CopilotAgent(BaseAgent):
    def __init__(self, llm: LLMProvider, router: ToolRouter, max_iterations: int = 5):
        super().__init__(llm, SYSTEM_PROMPT)
        self.router = router
        self.max_iterations = max_iterations

    async def run(self, history: list[dict]) -> str:
        """Run the agent over a conversation history and return the reply text.

        `history` is a list of {"role", "content"} messages (user/assistant).
        """
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            *history,
        ]
        tool_schemas = self.router.schemas()

        for _ in range(self.max_iterations):
            response = await self.llm.chat(messages, tools=tool_schemas)

            # No tool calls → this is the final answer.
            if not response.wants_tools:
                return response.content or ""

            # Record the assistant's tool-call request.
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

            # Execute each requested tool and feed results back.
            for tc in response.tool_calls:
                result = await self.router.execute(tc.name, tc.arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result.model_dump()),
                    }
                )

        # Hit the iteration cap — ask the model to answer with what it has.
        final = await self.llm.chat(messages)
        return final.content or (
            "I couldn't fully complete the request within the step limit."
        )

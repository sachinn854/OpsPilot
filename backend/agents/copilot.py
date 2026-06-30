"""
Copilot agent — a single agent with a tool-calling loop.

Flow:
  1. Build a dynamic system prompt from the tools registered in the router.
  2. Send conversation + available tool schemas to the LLM.
  3. If the LLM asks to call tools, run them via the Tool Router and feed the
     results back.
  4. Repeat until the LLM returns a normal answer (or we hit the step limit).
"""
import json

from backend.agents.base import BaseAgent
from backend.core.tool_router import ToolRouter
from backend.llm.base import LLMProvider
from backend.prompts.builder import (
    BASE_PROMPT,
    _available_sections,
    build_prompt_for_turn,
)


class CopilotAgent(BaseAgent):
    def __init__(self, llm: LLMProvider, router: ToolRouter, max_iterations: int = 5):
        tool_names = [s["function"]["name"] for s in router.schemas()]
        super().__init__(llm, BASE_PROMPT)
        self._available = _available_sections(tool_names)
        self.router = router
        self.max_iterations = max_iterations

    def _prompt_for(self, history: list[dict]) -> str:
        """Return a prompt tailored to the current conversation context."""
        return build_prompt_for_turn(BASE_PROMPT, history, self._available)

    async def run(self, history: list[dict]) -> str:
        messages: list[dict] = [
            {"role": "system", "content": self._prompt_for(history)},
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
                result_text = json.dumps(result.model_dump())
                if len(result_text) > 8000:
                    result_text = result_text[:8000] + "…[truncated]"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_text,
                    }
                )

        # Hit the iteration cap — ask the model to answer with what it has.
        final = await self.llm.chat(messages)
        return final.content or (
            "I couldn't fully complete the request within the step limit."
        )

    async def run_stream(self, history: list[dict]):
        messages: list[dict] = [
            {"role": "system", "content": self._prompt_for(history)},
            *history,
        ]
        tool_schemas = self.router.schemas()

        for _ in range(self.max_iterations):
            content = ""
            tool_calls = []
            async for ev in self.llm.chat_stream(messages, tools=tool_schemas):
                if ev["type"] == "token":
                    yield {"type": "token", "text": ev["text"]}
                elif ev["type"] == "done":
                    content = ev["content"]
                    tool_calls = ev["tool_calls"]

            # No tool calls → the streamed tokens were the final answer.
            if not tool_calls:
                yield {"type": "done", "text": content or ""}
                return

            # Record the assistant's tool-call request.
            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            # Execute each requested tool and feed results back.
            for tc in tool_calls:
                yield {"type": "tool", "name": tc.name}
                result = await self.router.execute(tc.name, tc.arguments)
                result_text = json.dumps(result.model_dump())
                if len(result_text) > 8000:
                    result_text = result_text[:8000] + "…[truncated]"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_text,
                    }
                )

        # Hit the iteration cap — stream a final answer with what we have.
        final_text = ""
        async for ev in self.llm.chat_stream(messages):
            if ev["type"] == "token":
                final_text += ev["text"]
                yield {"type": "token", "text": ev["text"]}
            elif ev["type"] == "done":
                final_text = ev["content"] or final_text
        yield {
            "type": "done",
            "text": final_text
            or "I couldn't fully complete the request within the step limit.",
        }

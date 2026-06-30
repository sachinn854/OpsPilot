"""
Copilot agent — a single agent with a tool-calling loop.

Flow:
  1. Send conversation + available tool schemas to the LLM.
  2. If the LLM asks to call tools, run them via the Tool Router and feed the
     results back.
  3. Repeat until the LLM returns a normal answer (or we hit the step limit).

This is the seed of the multi-agent system: this single loop is later split
into Planner → Research → Execution → Critic.
"""
import json

from backend.agents.base import BaseAgent
from backend.core.tool_router import ToolRouter
from backend.llm.base import LLMProvider

SYSTEM_PROMPT = """You are AI Operations Copilot, an autonomous enterprise assistant.

You help engineers with operational tasks: investigating issues, summarizing
GitHub activity, and answering questions. You can call tools to fetch live data.

## Core rule: ALWAYS use tools, NEVER ask for info you can fetch yourself.

GitHub — missing info resolution (follow this order, do NOT ask the user first):
1. No repo specified? → call `github_user_repos`, pick the most relevant repo by name.
2. No branch specified (e.g. for create_pr)? → call `github_branches` on the repo,
   pick the most recently active non-default branch as the source branch, then proceed.
3. No issue/PR number? → call `github_list_issues` or `github_list_prs` to find it.

Only ask the user if — after calling the appropriate tool — you genuinely have
multiple plausible options and cannot make a reasonable choice automatically.
In that case, show the fetched list and ask them to pick ONE item. Never ask
for information that a tool call could answer.

- A repository argument must always be in 'owner/name' format (e.g. 'alice/api').
- When a question is about internal knowledge (policies, manuals, uploaded docs),
  call `search_documents` and answer from the returned passages, citing source filenames.
- Base your answers ONLY on tool results. NEVER invent data. If a tool returns
  empty or an error, say so plainly — do not make up results.
- Be concise. Summarize results in a helpful, structured way.
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
        """Stream the agent's reply token-by-token.

        Yields event dicts:
          {"type": "tool", "name": str}   — a tool is being called
          {"type": "token", "text": str}  — a content delta of the final answer
          {"type": "done", "text": str}   — the complete final answer
        """
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
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

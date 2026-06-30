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

## CRITICAL: Never guess — always fetch first.

### GitHub repo resolution (MANDATORY steps, no exceptions):
- If the user mentions a repo name WITHOUT an owner (e.g. "CortexTutor", "my project"):
  → IMMEDIATELY call `github_user_repos` to get the full list of the user's repos.
  → Find the repo whose name matches (case-insensitive) and use its full "owner/name".
  → NEVER guess the owner. NEVER construct "name/name". NEVER ask the user for the owner.
- If no repo is mentioned at all:
  → call `github_user_repos`, pick the most recently pushed repo, proceed.
- If the full "owner/name" is already given (e.g. "sachinn854/CortexTutor"):
  → use it directly, no need to call `github_user_repos`.

### Branch resolution (when branch is needed but not specified):
→ call `github_branches` on the resolved repo.
→ pick the most recently active non-default branch as source.
→ NEVER ask the user for a branch name before trying this.

### Issue/PR resolution (when number is needed but not specified):
→ call `github_list_issues` or `github_list_prs` to find the right one.

### WRITE ACTIONS — always draft first, never act without confirmation (MANDATORY):

Write actions include: creating/updating/closing issues or PRs, posting Slack
messages, sending DMs, creating channels, merging PRs, creating branches,
restarting services, and any other action that changes something.

**The mandatory flow for every write action:**
1. Use read tools to gather all needed info (repo, branch, content, etc.).
2. Show the user a clear **draft preview** of exactly what will happen. Example:

   > I'll create this issue in **sachinn854/CortexTutor**:
   > **Title:** Fix login redirect bug
   > **Body:** Steps to reproduce…
   >
   > Shall I go ahead?

3. **STOP and wait** for the user to say yes / confirm / go ahead / ok.
4. Only AFTER explicit confirmation → call the write tool.
5. If the user says no / cancel / stop → do NOT call the tool. Ask what to change.

**NEVER call a write tool without showing a draft first and getting a yes.**
Not even for "simple" things like posting a message or adding a comment.

### Correction handling:
- If the user says "no", "I meant", "actually", "wait", "wrong" after you just
  did something → they are correcting that action, NOT asking for a new one.
  → Use an UPDATE tool on the existing item. NEVER create a duplicate.

### General rule:
Only ask the user when — after fetching — you have 2+ equally plausible choices
you cannot distinguish. Show the fetched list and ask them to pick ONE item.
Never ask for something a tool call could answer.

- Repo args must always be "owner/name" (e.g. "alice/api") — never just "name".
- For internal knowledge questions, call `search_documents` and cite source filenames.
- Base answers ONLY on tool results. Never invent data. Report errors plainly.
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

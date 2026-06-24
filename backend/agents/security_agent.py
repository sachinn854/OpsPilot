"""
Security agent.

Classifies whether achieving the goal requires a SENSITIVE action — one that
changes a live system (deploy/rollback/restart/delete/scale, sending external
messages, anything destructive or irreversible). If so, the run must pause for
human approval (HITL) before the Execution agent runs.

It combines two signals:
  - a deterministic backstop: does the plan/goal reference a known sensitive tool?
  - an LLM judgment for everything else.
The backstop wins — if a sensitive tool is clearly implied, we never rely on the
model to also catch it.
"""
from pydantic import BaseModel

from backend.agents.base import BaseAgent
from backend.agents.structured import complete_structured
from backend.llm.base import LLMProvider

SECURITY_PROMPT = """You are the Security classifier in a multi-agent operations copilot.

Decide whether accomplishing the goal requires a SENSITIVE action: one that
changes or disrupts a live system or is hard to reverse — e.g. deploying, rolling
back, restarting/scaling services, deleting data, changing access, or sending
messages to external parties. Read-only things (reading docs, listing issues,
summarizing, answering questions) are NOT sensitive.

Return JSON:
- sensitive: true only if a sensitive action is required.
- action: a short label for the action (e.g. "rollback api"), or "" if none.
- reason: one sentence explaining the classification."""


class SecurityVerdict(BaseModel):
    sensitive: bool
    action: str = ""
    reason: str = ""


class SecurityAgent(BaseAgent):
    def __init__(self, llm: LLMProvider, sensitive_tools: set[str] | None = None):
        super().__init__(llm, SECURITY_PROMPT)
        self.sensitive_tools = sensitive_tools or set()

    async def run(self, goal: str, *, plan_text: str = "") -> SecurityVerdict:
        """Classify the goal/plan as sensitive or safe."""
        # Deterministic backstop: a known sensitive tool named in the plan/goal.
        haystack = f"{goal}\n{plan_text}".lower()
        # Skip generic service-name prefixes (github, slack, jira) when extracting
        # the action verb — otherwise every GitHub goal would match "github".
        _SKIP_PREFIXES = {"github", "slack", "jira", "linear", "ops", "monitoring"}
        for tool in self.sensitive_tools:
            parts = tool.split("_")
            verb = parts[0] if parts[0] not in _SKIP_PREFIXES else (parts[1] if len(parts) > 1 else parts[0])
            if tool in haystack or verb in haystack:
                return SecurityVerdict(
                    sensitive=True,
                    action=tool.replace("_", " "),
                    reason=f"Goal/plan implies the sensitive '{tool}' action.",
                )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Goal: {goal}\n\nPlan:\n{plan_text}"},
        ]
        return await complete_structured(self.llm, messages, SecurityVerdict)

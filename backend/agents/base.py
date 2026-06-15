"""
Base agent.

In Phase 1 we have a single agent. From Phase 3 onward, specialized agents
(Planner, Research, Execution, Critic, ...) all build on this contract: an LLM
provider plus a system prompt that defines the agent's role.
"""
from backend.llm.base import LLMProvider


class BaseAgent:
    def __init__(self, llm: LLMProvider, system_prompt: str):
        self.llm = llm
        self.system_prompt = system_prompt

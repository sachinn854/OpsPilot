"""
Base agent.

A single agent to start with; specialized agents
(Planner, Research, Execution, Critic, ...) all build on this contract: an LLM
provider plus a system prompt that defines the agent's role.
"""
from backend.llm.base import LLMProvider


class BaseAgent:
    def __init__(self, llm: LLMProvider, system_prompt: str):
        self.llm = llm
        self.system_prompt = system_prompt

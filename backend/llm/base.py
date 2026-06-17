"""
LLM provider abstraction.

Agents NEVER call the Groq SDK directly — they go through this interface. That
keeps the provider swappable (Groq today, OpenAI/Anthropic/Ollama tomorrow) with
a one-line change.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A request from the model to call one of our tools."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """A normalized response from any LLM provider."""
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class LLMProvider(ABC):
    """Every LLM backend implements this single method."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Send a chat completion request and return a normalized response.

        `messages` follow the OpenAI/Groq message format. `tools` is an optional
        list of tool JSON schemas the model may call.
        """
        ...

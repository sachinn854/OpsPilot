"""
The standard Tool interface.

Every external capability (GitHub, Slack, DB, ...) implements this contract.
Agents never touch these directly — they call them via the Tool Router. Because
all tools share one shape, they can later be wrapped as MCP servers
without changing any agent code.
"""
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    """Uniform result returned by every tool."""
    ok: bool
    data: Any = None
    error: str | None = None


class Tool(ABC):
    # Subclasses set these as class attributes.
    name: str
    description: str
    parameters: dict  # JSON Schema describing the tool's arguments
    sensitive: bool = False  # True → needs human approval (HITL) before running

    @abstractmethod
    async def run(self, **kwargs) -> ToolResult:
        """Execute the tool with validated keyword arguments."""
        ...

    def to_openai_schema(self) -> dict:
        """Render this tool in the OpenAI/Groq function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

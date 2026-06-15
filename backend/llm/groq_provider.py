"""
Groq implementation of the LLMProvider interface.

Uses Groq's async client (OpenAI-compatible API), so tool-calling works with the
standard `tools` / `tool_calls` shape. The client is created lazily on first use
so the app can still boot (and serve /health) even if GROQ_API_KEY isn't set yet.
"""
import json

from groq import AsyncGroq

from backend.config import settings
from backend.llm.base import LLMProvider, LLMResponse, ToolCall


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.GROQ_API_KEY
        self._model = model or settings.GROQ_MODEL
        self._client: AsyncGroq | None = None

    @property
    def client(self) -> AsyncGroq:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "GROQ_API_KEY is not set. Add it to your .env file "
                    "(get a free key at https://console.groq.com)."
                )
            self._client = AsyncGroq(api_key=self._api_key)
        return self._client

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        tool_calls: list[ToolCall] = []
        for tc in message.tool_calls or []:
            try:
                arguments = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(id=tc.id, name=tc.function.name, arguments=arguments)
            )

        return LLMResponse(content=message.content, tool_calls=tool_calls)

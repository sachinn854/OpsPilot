"""
Groq implementation of the LLMProvider interface.

Uses Groq's async client (OpenAI-compatible API), so tool-calling works with the
standard `tools` / `tool_calls` shape. The client is created lazily on first use
so the app can still boot (and serve /health) even if GROQ_API_KEY isn't set yet.
"""
import json

from groq import AsyncGroq, BadRequestError

from backend.config import settings
from backend.llm.base import LLMProvider, LLMResponse, ToolCall
from backend.observability.metrics import LLM_REQUESTS_TOTAL, LLM_TOKENS_TOTAL


def _is_tool_use_failure(exc: BadRequestError) -> bool:
    """True if Groq rejected its own malformed tool call (retryable)."""
    try:
        return (exc.body or {}).get("error", {}).get("code") == "tool_use_failed"
    except Exception:
        return False


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

        # Groq's llama tool-calling parser occasionally rejects the model's own
        # (malformed) tool call with a `tool_use_failed` 400. Because generation
        # is stochastic, a couple of retries usually produce a valid call.
        response = None
        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                break
            except BadRequestError as exc:
                if _is_tool_use_failure(exc) and attempt < 2:
                    continue
                raise
        LLM_REQUESTS_TOTAL.labels(provider="groq").inc()
        if response.usage:
            LLM_TOKENS_TOTAL.labels(kind="prompt").inc(response.usage.prompt_tokens or 0)
            LLM_TOKENS_TOTAL.labels(kind="completion").inc(response.usage.completion_tokens or 0)

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

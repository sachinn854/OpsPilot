import json

from openai import AsyncOpenAI, BadRequestError, APIStatusError

from backend.config import settings
from backend.llm.base import LLMProvider, LLMResponse, ToolCall
from backend.observability.metrics import LLM_REQUESTS_TOTAL, LLM_TOKENS_TOTAL

_BASE_URL = "https://openrouter.ai/api/v1"
_EXTRA_HEADERS = {
    "HTTP-Referer": "https://github.com/ai-ops-copilot",
    "X-Title": "AI Operations Copilot",
}


class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.OPENROUTER_API_KEY
        self._model = model or settings.OPENROUTER_MODEL
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "OPENROUTER_API_KEY is not set. Add it to your .env file "
                    "(get a key at https://openrouter.ai/keys)."
                )
            self._client = AsyncOpenAI(
                base_url=_BASE_URL,
                api_key=self._api_key,
                default_headers=_EXTRA_HEADERS,
            )
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

        response = None
        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                break
            except BadRequestError as exc:
                msg = str(exc).lower()
                is_tool_err = (
                    "tool" in msg and ("validation" in msg or "schema" in msg or "failed" in msg)
                )
                if is_tool_err and attempt < 2:
                    continue
                if is_tool_err:
                    fallback = {k: v for k, v in kwargs.items() if k not in ("tools", "tool_choice")}
                    response = await self.client.chat.completions.create(**fallback)
                    break
                raise

        LLM_REQUESTS_TOTAL.labels(provider="openrouter").inc()
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

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
    ):
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        content_parts: list[str] = []
        tc_acc: dict[int, dict] = {}

        for attempt in range(3):
            content_parts = []
            tc_acc = {}
            streamed_any = False
            try:
                stream = await self.client.chat.completions.create(**kwargs)
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        content_parts.append(delta.content)
                        streamed_any = True
                        yield {"type": "token", "text": delta.content}
                    for tcd in delta.tool_calls or []:
                        slot = tc_acc.setdefault(
                            tcd.index, {"id": None, "name": None, "args": ""}
                        )
                        if tcd.id:
                            slot["id"] = tcd.id
                        if tcd.function and tcd.function.name:
                            slot["name"] = tcd.function.name
                        if tcd.function and tcd.function.arguments:
                            slot["args"] += tcd.function.arguments
                break
            except BadRequestError as exc:
                msg = str(exc).lower()
                is_tool_err = (
                    "tool" in msg and ("validation" in msg or "schema" in msg or "failed" in msg)
                )
                if is_tool_err and not streamed_any and attempt < 2:
                    continue
                if is_tool_err and not streamed_any:
                    fallback = {k: v for k, v in kwargs.items() if k not in ("tools", "tool_choice", "stream")}
                    resp = await self.client.chat.completions.create(**fallback)
                    text = resp.choices[0].message.content or ""
                    if text:
                        yield {"type": "token", "text": text}
                    yield {"type": "done", "content": text, "tool_calls": []}
                    return
                raise

        LLM_REQUESTS_TOTAL.labels(provider="openrouter").inc()

        tool_calls: list[ToolCall] = []
        for idx in sorted(tc_acc):
            slot = tc_acc[idx]
            if not slot["name"]:
                continue
            try:
                arguments = json.loads(slot["args"] or "{}")
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=slot["id"] or f"call_{idx}",
                    name=slot["name"],
                    arguments=arguments,
                )
            )

        yield {
            "type": "done",
            "content": "".join(content_parts),
            "tool_calls": tool_calls,
        }

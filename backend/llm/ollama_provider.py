"""
Ollama LLM provider — runs local models with tool-calling support.

Ollama exposes an OpenAI-compatible API at /v1, so we reuse the same
AsyncOpenAI client with a different base_url (no API key needed).

Start Ollama: https://ollama.com/download
Pull a model: ollama pull llama3.1

Models with reliable tool-calling support:
    llama3.1, llama3.2, llama3.3
    qwen2.5, qwen2.5-coder
    mistral-nemo, mistral-small
    phi4, phi3.5
    command-r
    granite3.1-dense
"""
import json
import logging

from openai import AsyncOpenAI, BadRequestError

from backend.llm.base import LLMProvider, LLMResponse, ToolCall
from backend.observability.metrics import LLM_REQUESTS_TOTAL, LLM_TOKENS_TOTAL

logger = logging.getLogger("copilot.ollama")


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str | None = None, model: str | None = None):
        from backend.config import settings
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model    = model or settings.OLLAMA_MODEL
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=f"{self._base_url}/v1",
                api_key="ollama",           # Ollama ignores the key but client requires it
            )
        return self._client

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        LLM_REQUESTS_TOTAL.labels(model=self._model, provider="ollama").inc()
        kwargs: dict = {"model": self._model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            resp = await self.client.chat.completions.create(**kwargs)
        except BadRequestError as exc:
            # Some Ollama models reject tool schemas — retry without tools
            if tools and "tool" in str(exc).lower():
                logger.warning("Ollama rejected tool schema, retrying without tools")
                resp = await self.client.chat.completions.create(
                    model=self._model, messages=messages
                )
            else:
                raise

        choice = resp.choices[0]
        msg    = choice.message

        usage = getattr(resp, "usage", None)
        if usage:
            LLM_TOKENS_TOTAL.labels(kind="prompt",     model=self._model).inc(usage.prompt_tokens or 0)
            LLM_TOKENS_TOTAL.labels(kind="completion", model=self._model).inc(usage.completion_tokens or 0)

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            wants_tools=bool(tool_calls),
        )

    async def chat_stream(self, messages: list[dict], tools: list[dict] | None = None):
        LLM_REQUESTS_TOTAL.labels(model=self._model, provider="ollama").inc()
        kwargs: dict = {
            "model":  self._model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"]       = tools
            kwargs["tool_choice"] = "auto"

        content    = ""
        tool_calls: list[ToolCall] = []
        tc_buffers: dict[int, dict] = {}

        try:
            stream = await self.client.chat.completions.create(**kwargs)
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                if delta.content:
                    content += delta.content
                    yield {"type": "token", "text": delta.content}

                if delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        idx = tc_chunk.index
                        if idx not in tc_buffers:
                            tc_buffers[idx] = {
                                "id":   tc_chunk.id or "",
                                "name": tc_chunk.function.name or "" if tc_chunk.function else "",
                                "args": "",
                            }
                        buf = tc_buffers[idx]
                        if tc_chunk.id:
                            buf["id"] = tc_chunk.id
                        if tc_chunk.function:
                            if tc_chunk.function.name:
                                buf["name"] += tc_chunk.function.name
                            if tc_chunk.function.arguments:
                                buf["args"] += tc_chunk.function.arguments

        except BadRequestError as exc:
            if tools and "tool" in str(exc).lower():
                logger.warning("Ollama stream: rejected tools, retrying without")
                async for ev in self.chat_stream(messages, tools=None):
                    yield ev
                return
            raise

        for buf in tc_buffers.values():
            try:
                args = json.loads(buf["args"] or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=buf["id"], name=buf["name"], arguments=args))

        yield {"type": "done", "content": content, "tool_calls": tool_calls}

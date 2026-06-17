"""
Structured LLM output helper (Phase 3).

Agents need typed, validated outputs (a Plan, a Verdict, ...), not free text.
This asks the LLM to return JSON matching a Pydantic schema, parses it robustly
(tolerates code fences / stray prose), validates it, and retries once with the
error fed back if the model gets it wrong.

All LLM access still goes through the `LLMProvider` abstraction (CLAUDE.md rule).
"""
import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from backend.llm.base import LLMProvider

T = TypeVar("T", bound=BaseModel)


def _extract_json(text: str) -> str:
    """Pull the JSON object out of an LLM reply (handles ```json fences / prose)."""
    s = text.strip()
    if s.startswith("```"):
        # strip the opening fence (``` or ```json) and the trailing fence
        s = s.split("\n", 1)[-1] if "\n" in s else s
        if s.endswith("```"):
            s = s[: -3]
        s = s.strip()
    # fall back to the first '{' .. last '}' span
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]
    return s


async def complete_structured(
    llm: LLMProvider,
    messages: list[dict],
    schema: type[T],
    *,
    temperature: float = 0.2,
) -> T:
    """Call the LLM and return a validated instance of `schema`.

    Raises ValueError if the model can't produce valid output after a retry.
    """
    guide = {
        "role": "system",
        "content": (
            "Respond with ONLY a single valid JSON object matching this JSON "
            "schema. No prose, no markdown, no code fences.\n"
            f"{json.dumps(schema.model_json_schema())}"
        ),
    }
    convo = [guide, *messages]

    last_err: Exception | None = None
    for _ in range(2):
        response = await llm.chat(convo, temperature=temperature)
        raw = response.content or ""
        try:
            data = json.loads(_extract_json(raw))
            return schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_err = exc
            convo.append({"role": "assistant", "content": raw})
            convo.append(
                {
                    "role": "user",
                    "content": (
                        f"That was not valid. Error: {exc}. "
                        "Return ONLY the corrected JSON object."
                    ),
                }
            )
    raise ValueError(f"LLM did not return valid {schema.__name__}: {last_err}")

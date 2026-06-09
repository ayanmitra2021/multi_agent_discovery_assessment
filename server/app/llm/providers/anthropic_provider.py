import json
from typing import TypeVar
from pydantic import BaseModel
import anthropic
from ..base import (
    ContentBlock,
    GenerateResponse,
    TextBlock,
    ThinkingBlock,
    ToolDefinition,
    ToolUseBlock,
)

T = TypeVar("T", bound=BaseModel)

_DEFAULT_MODEL = "claude-haiku-4-5"


class AnthropicProvider:
    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[ToolDefinition] = (),
        max_tokens: int = 8192,
        thinking: bool = True,
    ) -> GenerateResponse:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]
        if thinking:
            kwargs["thinking"] = {"type": "adaptive"}

        raw = await self._client.messages.create(**kwargs)
        return self._normalize(raw)

    async def generate_structured(
        self,
        messages: list[dict],
        output_type: type[T],
        system: str = "",
        max_tokens: int = 8192,
        thinking: bool = True,
    ) -> T:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": messages,
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_type.__name__,
                        "schema": output_type.model_json_schema(),
                    },
                }
            },
        }
        if system:
            kwargs["system"] = system
        if thinking:
            kwargs["thinking"] = {"type": "adaptive"}

        raw = await self._client.messages.create(**kwargs)

        text = next(
            (b.text for b in raw.content if hasattr(b, "text") and b.type == "text"),
            "",
        )
        return output_type.model_validate_json(text)

    def _normalize(self, raw) -> GenerateResponse:
        content: list[ContentBlock] = []
        for block in raw.content:
            if block.type == "text":
                content.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                content.append(
                    ToolUseBlock(id=block.id, name=block.name, input=block.input)
                )
            elif block.type == "thinking":
                content.append(ThinkingBlock(thinking=getattr(block, "thinking", "")))
        return GenerateResponse(
            content=content,
            stop_reason=raw.stop_reason,
            usage={
                "input_tokens": raw.usage.input_tokens,
                "output_tokens": raw.usage.output_tokens,
            },
            model=raw.model,
            raw=raw,
        )

import json
from typing import TypeVar
from pydantic import BaseModel
from openai import AsyncOpenAI
from ..base import (
    ContentBlock,
    GenerateResponse,
    TextBlock,
    ToolDefinition,
    ToolUseBlock,
)

T = TypeVar("T", bound=BaseModel)

_DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider:
    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def generate(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[ToolDefinition] = (),
        max_tokens: int = 8192,
        thinking: bool = True,  # ignored — OpenAI has no equivalent
    ) -> GenerateResponse:
        oai_messages = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        oai_messages.extend(messages)

        kwargs: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": oai_messages,
        }
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]

        raw = await self._client.chat.completions.create(**kwargs)
        msg = raw.choices[0].message
        finish_reason = raw.choices[0].finish_reason

        content: list[ContentBlock] = []
        if msg.content:
            content.append(TextBlock(text=msg.content))
        if msg.tool_calls:
            for tc in msg.tool_calls:
                content.append(
                    ToolUseBlock(
                        id=tc.id,
                        name=tc.function.name,
                        input=json.loads(tc.function.arguments),
                    )
                )

        stop_reason = "tool_use" if finish_reason == "tool_calls" else "end_turn"
        return GenerateResponse(
            content=content,
            stop_reason=stop_reason,
            usage={
                "input_tokens": raw.usage.prompt_tokens,
                "output_tokens": raw.usage.completion_tokens,
            },
            model=raw.model,
            raw=raw,
        )

    async def generate_structured(
        self,
        messages: list[dict],
        output_type: type[T],
        system: str = "",
        max_tokens: int = 8192,
        thinking: bool = True,
    ) -> T:
        oai_messages = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        oai_messages.extend(messages)

        raw = await self._client.beta.chat.completions.parse(
            model=self._model,
            max_tokens=max_tokens,
            messages=oai_messages,
            response_format=output_type,
        )
        return raw.choices[0].message.parsed

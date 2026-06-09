from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, runtime_checkable
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class TextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class ToolUseBlock:
    type: str = "tool_use"
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class ThinkingBlock:
    type: str = "thinking"
    thinking: str = ""


ContentBlock = TextBlock | ToolUseBlock | ThinkingBlock


@dataclass
class GenerateResponse:
    content: list[ContentBlock]
    stop_reason: str  # end_turn | tool_use | max_tokens
    usage: dict[str, int]  # input_tokens, output_tokens
    model: str
    raw: Any = None  # provider-specific response (for debugging)


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict


@runtime_checkable
class LLMClient(Protocol):
    """Provider-agnostic interface used by all agents."""

    async def generate(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[ToolDefinition] = (),
        max_tokens: int = 8192,
        thinking: bool = True,
    ) -> GenerateResponse:
        """
        Basic generation for agentic tool-use loops.
        Used by OrgPoliciesAgent for the MCP tool loop.
        """
        ...

    async def generate_structured(
        self,
        messages: list[dict],
        output_type: type[T],
        system: str = "",
        max_tokens: int = 8192,
        thinking: bool = True,
    ) -> T:
        """
        Structured output generation validated against a Pydantic model.
        Used by Discovery, Architecture, and Estimation agents.
        """
        ...

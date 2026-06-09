from ..config import Settings
from ..schemas.enums import LLMProvider
from .base import LLMClient
from .providers.anthropic_provider import AnthropicProvider
from .providers.openai_provider import OpenAIProvider


def create_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == LLMProvider.claude:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=claude")
        return AnthropicProvider(api_key=settings.anthropic_api_key)

    if settings.llm_provider == LLMProvider.openai:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAIProvider(api_key=settings.openai_api_key)

    raise ValueError(
        f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. "
        "Supported values: claude, openai"
    )

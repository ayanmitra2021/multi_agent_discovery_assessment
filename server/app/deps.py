from functools import lru_cache
from fastapi import Depends
from .config import Settings
from .llm.base import LLMClient
from .llm.factory import create_llm_client


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_llm_client(settings: Settings = Depends(get_settings)) -> LLMClient:
    return create_llm_client(settings)

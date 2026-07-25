from functools import cache

from agent.memory.extraction import LLMMemoryExtractor, MemoryExtractor
from agent.memory.resolution import LLMMemoryResolver, MemoryResolver
from agent.provider import LLMProvider, OpenAICompatibleLLMProvider
from agent.runtime.flow import Flow
from core.config import settings
from services.plan_execution import persist_plan


@cache
def get_llm_provider() -> LLMProvider:
    if settings.OPENAI_API_KEY is None:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    if settings.OPENAI_BASE_URL is None:
        raise RuntimeError("OPENAI_BASE_URL is not configured")

    if settings.OPENAI_MODEL is None:
        raise RuntimeError("OPENAI_MODEL is not configured")

    return OpenAICompatibleLLMProvider(
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        base_url=settings.OPENAI_BASE_URL,
        model=settings.OPENAI_MODEL,
    )


@cache
def get_agent_flow() -> Flow:
    return Flow(
        provider=get_llm_provider(),
        persist_plan=persist_plan,
    )


@cache
def get_memory_resolver() -> MemoryResolver:
    return LLMMemoryResolver(get_llm_provider())


@cache
def get_memory_extractor() -> MemoryExtractor:
    return LLMMemoryExtractor(get_llm_provider())

from agent.flow import Flow
from agent.long_term_memory import LLMMemoryResolver, MemoryResolver
from agent.memory_extractor import LLMMemoryExtractor, MemoryExtractor
from agent.provider import LLMProvider, OpenAICompatibleLLMProvider
from core.config import settings


_provider: LLMProvider | None = None
_flow: Flow | None = None
_memory_resolver: MemoryResolver | None = None
_memory_extractor: MemoryExtractor | None = None


def get_llm_provider() -> LLMProvider:
    global _provider

    if _provider is None:
        if settings.OPENAI_API_KEY is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        if settings.OPENAI_BASE_URL is None:
            raise RuntimeError("OPENAI_BASE_URL is not configured")

        if settings.OPENAI_MODEL is None:
            raise RuntimeError("OPENAI_MODEL is not configured")

        _provider = OpenAICompatibleLLMProvider(
            api_key=settings.OPENAI_API_KEY.get_secret_value(),
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
        )

    return _provider


def get_agent_flow() -> Flow:
    global _flow

    if _flow is None:
        _flow = Flow(provider=get_llm_provider())

    return _flow


def get_memory_resolver() -> MemoryResolver:
    global _memory_resolver

    if _memory_resolver is None:
        _memory_resolver = LLMMemoryResolver(get_llm_provider())

    return _memory_resolver


def get_memory_extractor() -> MemoryExtractor:
    global _memory_extractor

    if _memory_extractor is None:
        _memory_extractor = LLMMemoryExtractor(get_llm_provider())

    return _memory_extractor

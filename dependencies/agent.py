from agent.flow import Flow
from agent.provider import LLMProvider, OpenAICompatibleLLMProvider
from core.config import settings


_provider: LLMProvider | None = None
_flow: Flow | None = None


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
from agent.provider import (
    OpenAICompatiblePlanningProvider,
    PlanningProvider,
    PlanningProviderConfigurationError,
)
from core.config import settings
from exceptions.agent import AgentConfigurationError


_provider: OpenAICompatiblePlanningProvider | None = None


def get_planning_provider() -> PlanningProvider:
    global _provider

    if _provider is not None:
        return _provider

    api_key = settings.LLM_API_KEY
    base_url = settings.LLM_BASE_URL
    model = settings.LLM_MODEL

    if (
        api_key is None
        or base_url is None
        or model is None
    ):
        raise AgentConfigurationError()

    try:
        _provider = OpenAICompatiblePlanningProvider(
            api_key=api_key.get_secret_value(),
            base_url=base_url,
            model=model,
        )
    except PlanningProviderConfigurationError as exc:
        raise AgentConfigurationError() from exc

    return _provider


async def close_planning_provider() -> None:
    global _provider

    if _provider is None:
        return

    await _provider.close()
    _provider = None
